# infra — спільна інфраструктура CareerGuide

Піднімає спільні для всіх сервісів брокер подій, об'єктне сховище та кеш, а
також створює Docker-мережу `career-net`, до якої потім чіпляються
per-service compose-файли.

| Компонент | Образ | Порти (host) | Призначення |
|-----------|-------|--------------|-------------|
| **kafka** | `bitnami/kafka:3.7` (KRaft) | `29092` | Message Bus (`user-events`, `profession-events`, `resume-results`) |
| **minio** | `minio/minio` | `9000` (S3), `9001` (консоль) | S3-сумісне сховище (резюме, фото професій) |
| **minio-init** | `minio/mc` | — | створює бакет і заливає дефолтне фото, потім виходить |
| **redis** | `redis:7-alpine` | `6379` | in-memory кеш (TTL) |

> ⚠️ Баз даних тут немає. За принципом **database-per-service** кожен сервіс
> піднімає власний Postgres у власному `docker-compose.yml`.

## Передумови
- Docker + Docker Compose v2.
- Кореневий `.env` (необов'язково для інфри, але потрібен сервісам):
  ```bash
  cp ../.env.example ../.env
  ```

## Запуск

```bash
cd infra
docker compose up -d
```

Працює «з коробки» з дефолтними кредами MinIO (`minioadmin` / `minioadmin`).
Щоб узяти креди з кореневого `.env` (мають збігатися із значеннями, які
використовують сервіси):

```bash
docker compose --env-file ../.env up -d
```

Перевірити стан і дочекатися `healthy`:

```bash
docker compose ps
```

Зупинити (дані лишаються у томах) / прибрати разом з даними:

```bash
docker compose down
docker compose down -v        # також видалити томи kafka/minio/redis
```

## MinIO

- Консоль: <http://localhost:9001> (логін/пароль — `S3_ACCESS_KEY` / `S3_SECRET_KEY`,
  дефолт `minioadmin` / `minioadmin`).
- S3 API: <http://localhost:9000>.
- Бакет `career-guide` створюється автоматично (`minio-init`).

Розкладка об'єктів:
- фото професій — `professions/{profession_id}.{jpg|png|webp}`, дефолт `professions/_default.jpg`;
- резюме — `resumes/{user_id}/{uuid}.pdf`.

### Залити фото професії вручну
Поклади дефолтне фото в `infra/assets/profession-default.jpg` (його залиє
`minio-init` як `_default.jpg`), або завантаж фото конкретної професії через `mc`:

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin
mc cp photo.jpg local/career-guide/professions/42.jpg
mc ls local/career-guide/professions/
```

## Kafka

Перевірити, що брокер живий, і переглянути топіки:

```bash
docker compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Топіки створюються автоматично при першій публікації (`AUTO_CREATE_TOPICS_ENABLE=true`,
`partition=1`): `user-events`, `profession-events`, `resume-results`.

Створити топік явно / подивитися повідомлення:

```bash
docker compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --if-not-exists --topic user-events --partitions 1 --replication-factor 1

docker compose exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic user-events --from-beginning
```

Адресація брокера:
- з **Docker**-контейнерів (сервіси в мережі `career-net`): `kafka:9092`;
- з **локального** процесу (uvicorn на хості): `localhost:29092`.

## Redis

```bash
docker compose exec redis redis-cli ping        # -> PONG
```

- з Docker: `redis://redis:6379/0`;
- локально: `redis://localhost:6379/0`.

## Мережа `career-net`

Цей compose створює зовнішню мережу з фіксованою назвою `career-net`. Кожен
per-service `docker-compose.yml` підключається до неї як external:

```yaml
networks:
  career-net:
    external: true
```

Перевірити:

```bash
docker network inspect career-net
```

## Що далі

1. Підняти інфру (цей каталог).
2. Підняти потрібні сервіси їхніми власними compose-файлами — кожен тягне свою
   БД і чіпляється до `career-net`, щоб бачити `kafka` / `minio` / `redis` за
   внутрішніми іменами. Приклад-зразок: `backend/user-service/docker-compose.yml`:
   ```bash
   cd backend/user-service
   docker compose --env-file ../../.env up -d --build
   ```
3. Для запуску всього бекенда разом — Kubernetes-маніфести в `k8s/`.
