import { AuthForm } from "@/components/AuthForms";

interface RegisterPageProps {
  searchParams: Promise<{ error?: string }>;
}

export default async function RegisterPage({ searchParams }: RegisterPageProps) {
  return <AuthForm mode="register" initialError={(await searchParams).error ?? ""} />;
}
