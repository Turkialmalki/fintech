import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-6 text-center">
      <div>
        <p className="text-[13px] text-muted">404</p>
        <h1 className="mt-1 text-[22px] font-semibold">الصفحة غير موجودة · Page not found</h1>
        <Link href="/" className="mt-4 inline-block text-[14px] font-medium text-primary hover:underline">العودة إلى نظرة عامة · Back to overview</Link>
      </div>
    </main>
  );
}
