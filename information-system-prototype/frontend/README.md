# CareerGuide — Frontend

The client of the CareerGuide career-orientation recommender, built with **Next.js
(App Router) + React + TypeScript + Tailwind CSS** and server-side rendering. White
surfaces, a blue brand palette, adaptive across phone / tablet / desktop.

The frontend is a **BFF (backend-for-frontend)**: the browser only ever talks to
Next.js (Route Handlers, Server Components, Server Actions); Next.js calls the
**API Gateway** server-side and attaches the JWT, which is stored in httpOnly
cookies. The gateway is the single entry point to all backend services.

## Prerequisites

- **Node.js 20+** (Linux-native; on WSL use a Linux Node such as `nvm`, not the
  Windows install).
- The **API Gateway** running and reachable (and, behind it, the backend services
  + shared infra). See `infra/` and `backend/`.

## Environment

```bash
cp .env.local.example .env.local
```

| Variable        | Default                 | Purpose                                            |
| --------------- | ----------------------- | -------------------------------------------------- |
| `GATEWAY_URL`   | `http://localhost:8000` | Base URL of the API Gateway (server-side only).    |
| `COOKIE_SECURE` | `false`                 | Set `true` behind HTTPS so auth cookies are Secure. |

## Local development

```bash
npm install
npm run dev          # http://localhost:3000
```

Other scripts:

```bash
npm run build        # production build (standalone output)
npm run start        # run the production build
npm run lint         # ESLint
npm run typecheck    # tsc --noEmit
```

> The gateway (and the services behind it) must be up. With the default
> `.env.local`, the app expects the gateway at `http://localhost:8000`.

## Docker

```bash
cd frontend
docker compose up -d --build      # publishes http://localhost:3000
```

The container reaches the gateway at `http://career-api-gateway:8000` over the
shared external `career-net` network (created by `infra/docker-compose.yml`).
Start the infra and `backend/api-gateway` first.

## Routes (mapped to functional requirements)

| Route                              | Purpose                                                       |
| ---------------------------------- | ------------------------------------------------------------- |
| `/`                                | Public landing (redirects signed-in users to recommendations). |
| `/register`, `/login`              | Registration (FR1) and login (FR2).                           |
| `/forgot-password`, `/reset-password` | Password reset (FR3).                                      |
| `/verify`                          | Email confirmation (FR7).                                     |
| `/profile`                         | Profile overview (FR4) + change password (FR3).               |
| `/profile/edit`                    | Edit profile or upload a résumé (FR5/FR1).                    |
| `/riasec`                          | RIASEC interest assessment (FR6).                             |
| `/recommendations`                 | Ranked professions with sort/filter (FR10).                   |
| `/recommendations/settings`        | Recommendation criteria (FR8).                                |
| `/professions`                     | Search; recommended float to the top (FR9).                   |
| `/professions/[id]`                | Profession details with skill highlighting (FR11).            |
| `/chats`, `/chats/[id]`            | Assistant chats (FR12, FR16–FR19).                            |
| `/admin/professions/*`             | Admin CRUD + photo upload (FR13–FR15, admin only).            |

## Notes on asynchronous flows

- **Résumé parsing** (`/profile/edit`) and **recommendation readiness**
  (`/recommendations`) are asynchronous on the backend (a worker processes them).
  The UI polls and updates automatically (TanStack Query + `router.refresh()`).
- **Auth refresh** is proactive: middleware exchanges the refresh-token cookie for
  a fresh access token before a protected page renders, so SSR always sees a valid
  token. The gateway fetch wrapper also refreshes once on a 401.

## Structure

```
src/
├── middleware.ts          # route guards + proactive token refresh
├── app/
│   ├── (auth)/            # login / register / verify / reset
│   ├── (app)/             # authenticated shell: profile, reco, professions, chats, admin
│   ├── layout.tsx         # root layout + providers
│   └── page.tsx           # public landing
├── actions/               # Server Actions (auth, profile, reco, chat, admin)
├── components/            # UI primitives + feature components
└── lib/
    ├── api/               # typed gateway clients (users, career, reco, chat)
    ├── auth/              # cookies + session
    ├── types.ts           # DTOs mirroring the backend schemas
    └── …                  # industries, criteria, riasec, formatting helpers
```

## Conventions / design

- Blue brand scale exposed as `brand-*` Tailwind utilities (see `globals.css`).
- All user-facing copy is in **English**.
- Industry values use the recommender's UPPERCASE keys (e.g.
  `INFORMATION-TECHNOLOGY`) with human-readable labels in the UI.
- Photos and résumé downloads use presigned S3/MinIO URLs returned by the backend.
  In Docker, browser-facing presigned URLs require the MinIO endpoint to be
  reachable from the browser (an infra/CORS concern, not the frontend's).
```
