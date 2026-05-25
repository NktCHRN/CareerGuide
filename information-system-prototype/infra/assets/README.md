# infra/assets

Сюди кладуть статичні файли, які `minio-init` заливає в MinIO при підйомі
спільної інфри.

## `profession-default.jpg`
Дефолтне фото професії. Якщо файл лежить тут, `minio-init` заливає його як
`career-guide/professions/_default.jpg` (об'єкт, який віддається для професій
без власного фото).

Файл версіонується у git (виняток у кореневому `.gitignore`:
`!infra/assets/profession-default.jpg`). Якщо його немає — `minio-init`
просто пропускає цей крок, помилки не буде.

Залити фото конкретної професії вручну (після підйому інфри):

```bash
mc alias set local http://localhost:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
mc cp photo.jpg local/career-guide/professions/42.jpg
```
