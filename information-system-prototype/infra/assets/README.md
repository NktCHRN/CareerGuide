# infra/assets

This is where static files are placed that `minio-init` uploads to MinIO when the
shared infra is brought up.

## `profession-default.jpg`
The default profession photo. If the file is present here, `minio-init` uploads it as
`career-guide/professions/_default.jpg` (the object served for professions that have
no photo of their own).

The file is versioned in git (an exception in the root `.gitignore`:
`!infra/assets/profession-default.jpg`). If it is missing, `minio-init` simply
skips this step — there will be no error.

Upload a photo for a specific profession manually (after bringing up the infra):

```bash
mc alias set local http://localhost:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
mc cp photo.jpg local/career-guide/professions/42.jpg
```
