import { requireAdmin } from "@/lib/auth/session";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Gate the entire admin area to administrators (redirects others away).
  await requireAdmin();
  return <>{children}</>;
}
