# user-service — Керування акаунтом користувача

Мікросервіс **UserService** системи CareerGuide (C4, табл. 4.2): автентифікація
(єдиний емітент JWT), профіль користувача та резюме. Зберігає резюме в S3 і
надсилає листи (SES, за фіче-флагом), але **НЕ парсить резюме** — парсинг робить
recommendation-worker, а результат повертається назад через шину Kafka.

- **Порт:** `8001`
- **База:** `userdb` (PostgreSQL 16)
- **Стек:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x (async, asyncpg) ·
  Alembic · aiokafka · boto3 · redis · passlib[bcrypt] · python-jose

## Функціонал (ФВ1–ФВ8)

| Група | Ендпойнти |
|-------|-----------|
| Автентифікація | `register`, `login`, `refresh`, `verify-email`, `request-password-reset`, `reset-password`, `change-password` |
| Профіль | `GET/PUT /api/profile/me`, `PATCH /api/profile/me/criteria` |
| Резюме | `POST /api/profile/me/resume`, `GET /api/profile/me/resumes` |
| Довідники | `GET /api/industries`, `GET /api/recommendation-criteria` |
| Службове | `GET /api/health` |

Усі ендпойнти під префіксом `/api`. Інтерактивна документація: `/docs`.

## Події Kafka

**Публікує** (топік `user-events`):
- `user.profile.updated` — при зміні `summary` / `skills` / `experiences` або
  `recommendation_criteria` (запускає у worker обчислення вектора й мапінг навичок);
- `user.resume.uploaded` — `{user_id, s3_key}` після завантаження PDF (підхоплює worker);
- `user.deleted` — при видаленні акаунта.

**Споживає** (топік `resume-results`, група `user-resume-results`, ідемпотентно):
- `user.profile.parsed` — мердж розпарсеного резюме у профіль → зберігає й
  **публікує** `user.profile.updated`;
- `user.esco_skills.mapped` — зберігає змаповані ESCO-навички у поле `esco_skills`;
  `user.profile.updated` **НЕ** публікує (інакше — нескінченний цикл).

## Режими автентифікації (`AUTH_MODE`)
- `local` (default для ізольованого dev) — сервіс сам валідує JWT тим самим `JWT_SECRET`;
- `gateway` (K8s/прод) — довіряє заголовкам `X-User-Id` / `X-User-Role` від API Gateway.

JWT — HS256. Payload access: `{sub, role, email, type:"access", exp}`. Видає токени
**лише** цей сервіс (access ~30 хв, refresh ~30 днів).

---

## Запуск через Docker (рекомендовано)

Передумова — піднята спільна інфра (Kafka/MinIO/Redis) і мережа `career-net`:

```bash
cd ../../infra && docker compose up -d        # один раз; деталі — infra/README.md
```

Потім сам сервіс (піднімає `userdb` + `user-service`, виконує міграції+сідинг):

```bash
cd backend/user-service
docker compose --env-file ../../.env up -d --build
curl http://localhost:8001/api/health
```

## Локальний запуск (venv + uvicorn)

Сервіс ходить у спільну інфру через прокинуті назовні порти (Kafka `29092`,
MinIO `9000`, Redis `6379`) — значення в кореневому `.env` уже на localhost.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# БД для локального запуску: або підніми лише userdb з docker-compose
#   docker compose --env-file ../../.env up -d userdb
# (контейнер мапить userdb на localhost:5433 — саме цей DSN у дефолтах config.py)

alembic upgrade head                 # схема + ідемпотентний сід (адмін, демо-користувач)
uvicorn app.main:app --reload --port 8001
```

Конфіг читає кореневий `../../.env` (а за наявності — локальний `.env` сервіса,
який перекриває кореневий; шаблон — `.env.example`).

### Сід-акаунти (з `.env`, `SEED_*`)
| Роль | Email | Пароль |
|------|-------|--------|
| admin | `admin@career-guide.local` | `admin12345` |
| user  | `user@career-guide.local`  | `user12345` (з демо-профілем) |

### Backfill векторів
Після першого запуску — опублікувати `user.profile.updated` для всіх профілів,
щоб worker порахував вектори:

```bash
python -m app.events.backfill_users
```

---

## Приклади `curl`

```bash
B=http://localhost:8001

# 1) Реєстрація (з профілем). У dev повертається email_verification_token.
curl -s -X POST $B/api/auth/register -H 'Content-Type: application/json' -d '{
  "email":"alice@example.com","password":"supersecret1",
  "profile":{"name":"Alice","summary":"Backend developer",
    "skills":["Python","FastAPI","SQL"],
    "experiences":[{"title":"Backend Developer","industry":"INFORMATION-TECHNOLOGY",
                    "start":"5/2019","end":"current"}]}}'

# 2) Логін → access/refresh
ACCESS=$(curl -s -X POST $B/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"supersecret1"}' | jq -r .access_token)

# 3) Профіль
curl -s $B/api/profile/me -H "Authorization: Bearer $ACCESS"

# 4) Оновлення профілю (тягне подію user.profile.updated)
curl -s -X PUT $B/api/profile/me -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d '{"summary":"Data engineer","skills":["python","sql"]}'

# 5) Критерії рекомендацій (тягне user.profile.updated)
curl -s -X PATCH $B/api/profile/me/criteria -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' -d '{"recommendation_criteria":["experience","hobbies"]}'

# 6) Завантаження резюме → S3 + подія user.resume.uploaded
curl -s -X POST $B/api/profile/me/resume -H "Authorization: Bearer $ACCESS" \
  -F "file=@cv.pdf;type=application/pdf"
curl -s $B/api/profile/me/resumes -H "Authorization: Bearer $ACCESS"
```

Переконатися, що подія пішла:

```bash
cd ../../infra
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic user-events --from-beginning
# → побачиш user.profile.updated та user.resume.uploaded
```

---

## Модель даних (`userdb`)
`users` · `profiles` · `profile_experiences` · `esco_skills` · `email_tokens` · `resumes`.

- `experiences[].industry` — ключ `industry_to_id` у UPPERCASE (напр.
  `INFORMATION-TECHNOLOGY`) або `null`; саме так очікує модель worker. Список
  ключів із підписами для випадаючого списку — `GET /api/industries`.
- `experiences[].start` — `"M/YYYY"`; `end` — `"M/YYYY"` | `"current"` | `null`;
  `months_of_experience` рахується автоматично, якщо не задано.
- `recommendation_criteria` ⊆ `{experience, psychological, hobbies, competencies}`,
  default `{experience}`. **У прототипі реально працює лише `experience`**; інші
  критерії приймаються й зберігаються як задача на майбутнє.

## Фіче-флаг листів (SES)
`FEATURE_EMAIL_ENABLED` (default `false`). При `false` листи не надсилаються
(лог), і в `APP_ENV=dev` ендпойнти повертають токен у відповіді
(`email_verification_token`, `dev_token`). При `true` лист іде через AWS SES, а
токени у відповіді не повертаються.

## Кеш
Зібраний профіль (`GET /api/profile/me`) кешується в Redis
(`user:profile:{id}`, TTL `PROFILE_CACHE_TTL_SECONDS`) і скидається при будь-якій
зміні профілю. Redis — best-effort: його недоступність не валить запити.
