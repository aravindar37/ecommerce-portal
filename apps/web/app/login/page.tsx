import { AuthForm } from "@/components/AuthForms";

interface LoginPageProps {
  searchParams: Promise<{ error?: string; returnTo?: string }>;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  return <AuthForm mode="login" initialError={params.error ?? ""} returnTo={params.returnTo ?? "/products"} />;
}
