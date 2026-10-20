"use client";

// Workspace strings in English and Arabic. Identifiers (part numbers, serials, ids) are never
// translated and are isolated with <bdi> where they appear inside Arabic text.

import { createContext, useContext, type JSX, type ReactNode } from "react";

export type AppLocale = "en" | "ar";

const EN = {
  "nav.workspace": "Workspace",
  "nav.dashboard": "Dashboard",
  "nav.new": "New enquiry",
  "nav.enquiries": "Enquiries",
  "nav.machines": "Saved machines",
  "nav.review": "Review queue",
  "nav.admin": "Administration",
  "nav.users": "Users & access",
  "nav.catalogue": "Catalogue",
  "nav.imports": "Imports",
  "nav.analytics": "Analytics",
  "nav.jobs": "Jobs & operations",
  "nav.audit": "Audit trail",
  "nav.evaluation": "Evaluation",
  "nav.account": "Account",
  "nav.scenarios": "Guided scenarios",
  "nav.how": "How it works",
  "shell.demo": "Public demo · synthetic data",
  "shell.account": "Signed in",
  "shell.preview": "Preview as",
  "shell.customer": "Customer",
  "shell.reviewer": "Reviewer",
  "shell.admin": "Administrator",
  "shell.reset": "Reset demo",
  "shell.signout": "Sign out",
  "shell.menu": "Menu",
  "shell.close": "Close menu",
  "shell.skip": "Skip to content",
  "common.retry": "Try again",
  "common.loading": "Loading…",
  "common.empty": "Nothing here yet.",
  "common.cancel": "Cancel",
  "common.confirm": "Confirm",
  "common.save": "Save",
  "common.open": "Open",
  "common.back": "Back",
  "common.search": "Search",
  "common.all": "All",
  "common.next": "Next",
  "common.previous": "Previous",
  "common.notMeasured": "Not measured",
  "status.received": "Received",
  "status.processing": "Processing",
  "status.needs_information": "Needs your input",
  "status.awaiting_review": "In human review",
  "status.approved": "Answered",
  "status.rejected": "Returned by reviewer",
  "status.failed": "Needs staff attention",
  "entry.title": "Choose how to enter",
  "entry.demo": "Try the demo",
  "entry.demoBody": "No account needed. You get a private, disposable workspace with synthetic data and can preview the customer, reviewer and administrator views.",
  "entry.signin": "Sign in",
  "entry.signinBody": "Invited customers and staff sign in with their PartsIQ account.",
  "entry.expired": "Your session has ended. Sign in again to continue.",
};

type Key = keyof typeof EN;

const AR: Record<Key, string> = {
  "nav.workspace": "مساحة العمل",
  "nav.dashboard": "لوحة المتابعة",
  "nav.new": "طلب جديد",
  "nav.enquiries": "الطلبات",
  "nav.machines": "الماكينات المحفوظة",
  "nav.review": "قائمة المراجعة",
  "nav.admin": "الإدارة",
  "nav.users": "المستخدمون والصلاحيات",
  "nav.catalogue": "الكتالوج",
  "nav.imports": "الاستيراد",
  "nav.analytics": "التحليلات",
  "nav.jobs": "المهام والتشغيل",
  "nav.audit": "سجل التدقيق",
  "nav.evaluation": "التقييم",
  "nav.account": "الحساب",
  "nav.scenarios": "سيناريوهات موجهة",
  "nav.how": "كيف يعمل",
  "shell.demo": "عرض تجريبي عام · بيانات اصطناعية",
  "shell.account": "تم تسجيل الدخول",
  "shell.preview": "عرض بصفة",
  "shell.customer": "عميل",
  "shell.reviewer": "مراجع",
  "shell.admin": "مسؤول",
  "shell.reset": "إعادة ضبط العرض",
  "shell.signout": "تسجيل الخروج",
  "shell.menu": "القائمة",
  "shell.close": "إغلاق القائمة",
  "shell.skip": "تخطَّ إلى المحتوى",
  "common.retry": "حاول مجددًا",
  "common.loading": "جارٍ التحميل…",
  "common.empty": "لا يوجد شيء بعد.",
  "common.cancel": "إلغاء",
  "common.confirm": "تأكيد",
  "common.save": "حفظ",
  "common.open": "فتح",
  "common.back": "رجوع",
  "common.search": "بحث",
  "common.all": "الكل",
  "common.next": "التالي",
  "common.previous": "السابق",
  "common.notMeasured": "غير مقاس",
  "status.received": "مستلم",
  "status.processing": "قيد المعالجة",
  "status.needs_information": "بحاجة إلى ردك",
  "status.awaiting_review": "قيد المراجعة البشرية",
  "status.approved": "تم الرد",
  "status.rejected": "أعاده المراجع",
  "status.failed": "يحتاج متابعة الموظفين",
  "entry.title": "اختر طريقة الدخول",
  "entry.demo": "جرّب العرض",
  "entry.demoBody": "بدون حساب. تحصل على مساحة خاصة مؤقتة ببيانات اصطناعية ويمكنك معاينة واجهة العميل والمراجع والمسؤول.",
  "entry.signin": "تسجيل الدخول",
  "entry.signinBody": "العملاء والموظفون المدعوون يسجلون الدخول بحساب PartsIQ.",
  "entry.expired": "انتهت جلستك. سجّل الدخول مجددًا للمتابعة.",
};

const LocaleContext = createContext<AppLocale>("en");

export function AppLocaleProvider({ locale, children }: { locale: AppLocale; children: ReactNode }): JSX.Element {
  return <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>;
}

export function useLocale(): AppLocale {
  return useContext(LocaleContext);
}

export function useT(): (key: Key) => string {
  const locale = useContext(LocaleContext);
  return (key: Key) => (locale === "ar" ? AR[key] : EN[key]) ?? EN[key];
}

export type { Key as TKey };
