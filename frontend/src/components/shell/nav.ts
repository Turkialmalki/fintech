import {
  Activity, Bot, BookOpenText, ClipboardCheck, FileStack, LayoutGrid, Plug, ScanSearch, Settings, ShieldCheck, Sparkles,
} from "lucide-react";
import type { Dict } from "@/lib/dictionaries";

export type NavItem = { href: string; key: keyof Dict["nav"]; icon: React.ElementType; perm?: string };

export const NAV: { group: keyof Dict["nav"]; items: NavItem[] }[] = [
  { group: "groupWork", items: [
    { href: "/", key: "overview", icon: LayoutGrid },
    { href: "/applications", key: "applications", icon: FileStack, perm: "applications:read" },
    { href: "/intelligence", key: "intelligence", icon: ScanSearch, perm: "regulatory:read" },
    { href: "/assessments", key: "assessments", icon: Sparkles, perm: "assessments:read" },
    { href: "/reviews", key: "reviews", icon: ClipboardCheck, perm: "assessments:read" },
  ] },
  { group: "groupAI", items: [
    { href: "/agents", key: "agents", icon: Bot, perm: "assessments:read" },
    { href: "/integrations", key: "integrations", icon: Plug, perm: "applications:read" },
    { href: "/knowledge", key: "knowledge", icon: BookOpenText, perm: "regulatory:read" },
  ] },
  { group: "groupControl", items: [
    { href: "/governance", key: "governance", icon: ShieldCheck, perm: "governance:read" },
    { href: "/audit", key: "audit", icon: Activity, perm: "audit:read" },
    { href: "/settings", key: "settings", icon: Settings },
  ] },
];
