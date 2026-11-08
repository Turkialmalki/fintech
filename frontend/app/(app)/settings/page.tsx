"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Radar } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Segmented, Select } from "@/components/ui/field";
import { Notice, SkeletonRows } from "@/components/ui/feedback";
import { DescList, PageHeader, Panel, TabPanel, Tabs } from "@/components/ui/layout";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { labels } from "@/lib/dictionaries";
import { useI18n } from "@/lib/i18n";
import type { User } from "@/lib/types";

type AIConfig = { active: { provider: string; model: string; base_url: string; api_key_configured: boolean; source: string; is_mock: boolean; capabilities: Record<string, unknown> };
  embedding: { provider: string; model: string; dim: number; is_mock: boolean }; providers: Record<string, { base_url_configured: boolean; api_key_configured: boolean; default_model: string }>;
  vector_backend: string; temperature: number; max_tokens: number };

export default function Settings() {
  const { t, can } = { ...useI18n(), ...useAuth() };
  const [tab, setTab] = useState("profile");
  return (
    <div>
      <PageHeader title={t.settings.title} subtitle={t.settings.subtitle} />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "profile", label: t.settings.profile },
        ...(can("users:manage") ? [{ value: "users", label: t.settings.users }] : []),
        ...(can("governance:read") ? [{ value: "ai", label: t.settings.ai }] : []),
        ...(can("settings:manage") ? [{ value: "system", label: t.settings.system }] : [])]}>
        <TabPanel value="profile"><Profile /></TabPanel>
        <TabPanel value="users"><Users /></TabPanel>
        <TabPanel value="ai"><AI /></TabPanel>
        <TabPanel value="system"><SystemTab /></TabPanel>
      </Tabs>
    </div>
  );
}

function Profile() {
  const { t, pick, locale, setLocale, label } = useI18n();
  const { me } = useAuth();
  if (!me) return <SkeletonRows />;
  return (
    <div className="grid max-w-4xl gap-6 lg:grid-cols-2">
      <Panel title={t.settings.profile}>
        <DescList cols={1} items={[{ label: t.settings.fullNameAr, value: me.full_name_ar }, { label: t.settings.fullNameEn, value: me.full_name_en },
          { label: t.login.email, value: <span className="ltr">{me.email}</span> }, { label: t.settings.roles, value: me.role_codes.map((r) => label("role", r)).join("، ") },
          { label: pick("الجهة", "Organization"), value: pick(me.organization.name_ar, me.organization.name_en) }]} />
      </Panel>
      <Panel title={t.settings.languagePref}>
        <Segmented value={locale} onChange={(l) => { setLocale(l); api("/auth/me/preferences", { method: "PATCH", body: { preferred_locale: l } }).catch(() => undefined); }}
          options={[{ value: "ar", label: t.settings.arabic }, { value: "en", label: t.settings.english }]} />
      </Panel>
    </div>
  );
}

function Users() {
  const { t, pick, label, locale } = useI18n();
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/users") });
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email: "", full_name_ar: "", full_name_en: "", password: "", roles: ["analyst"] });
  const create = useMutation({ mutationFn: () => api("/users", { body: f }), onSuccess: () => { toast.success(t.settings.userCreated); setOpen(false); qc.invalidateQueries({ queryKey: ["users"] }); },
    onError: (e) => toast.error(errorText(e, locale)) });
  const toggle = useMutation({ mutationFn: (u: User) => api(`/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }), onError: (e) => toast.error(errorText(e, locale)) });
  return (
    <div className="rounded-xl border border-line bg-surface">
      <div className="flex justify-end border-b border-line px-5 py-3"><Button size="sm" onClick={() => setOpen(true)}><Plus />{t.settings.addUser}</Button></div>
      {!users.data ? <SkeletonRows className="p-5" /> : (
        <Table>
          <thead><tr><Th>{t.settings.fullNameAr}</Th><Th>{t.login.email}</Th><Th>{t.settings.roles}</Th><Th>{t.common.status}</Th><Th /></tr></thead>
          <tbody>{users.data.map((u) => (
            <Tr key={u.id}>
              <Td className="font-medium">{pick(u.full_name_ar, u.full_name_en)}<p className="text-[12px] font-normal text-muted">{pick(u.title_ar, u.title_en)}</p></Td>
              <Td className="ltr text-start text-[12.5px]">{u.email}</Td>
              <Td>{u.role_codes.map((r) => <Badge key={r} className="me-1">{label("role", r)}</Badge>)}</Td>
              <Td><Badge tone={u.is_active ? "success" : "neutral"} dot>{u.is_active ? t.settings.active : t.settings.inactive}</Badge></Td>
              <Td className="text-end"><Button size="sm" variant="ghost" onClick={() => toggle.mutate(u)}>{u.is_active ? pick("تعطيل", "Disable") : pick("تفعيل", "Enable")}</Button></Td>
            </Tr>))}
          </tbody>
        </Table>
      )}
      <Dialog open={open} onOpenChange={setOpen} title={t.settings.addUser}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>{t.common.cancel}</Button><Button loading={create.isPending} onClick={() => create.mutate()}>{t.common.create}</Button></>}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.settings.fullNameAr}><Input value={f.full_name_ar} onChange={(e) => setF({ ...f, full_name_ar: e.target.value })} /></Field>
          <Field label={t.settings.fullNameEn}><Input dir="ltr" value={f.full_name_en} onChange={(e) => setF({ ...f, full_name_en: e.target.value })} /></Field>
          <Field label={t.login.email}><Input dir="ltr" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label={t.login.password} hint={pick("10 أحرف على الأقل", "At least 10 characters")}><Input dir="ltr" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <fieldset className="sm:col-span-2"><legend className="mb-2 text-[13px] font-medium text-ink-2">{t.settings.roles}</legend>
            <div className="flex flex-wrap gap-4">{Object.keys(labels.role).map((r) => (
              <Checkbox key={r} label={label("role", r)} checked={f.roles.includes(r)} onChange={(v) => setF({ ...f, roles: v ? [...f.roles, r] : f.roles.filter((x) => x !== r) })} />))}</div>
          </fieldset>
        </div>
      </Dialog>
    </div>
  );
}

function AI() {
  const { t, pick, locale } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["ai-config"], queryFn: () => api<AIConfig>("/ai/config") });
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const switchM = useMutation({ mutationFn: () => api("/ai/config", { method: "PUT", body: { provider, model } }),
    onSuccess: () => { toast.success(t.settings.switched); qc.invalidateQueries(); }, onError: (e) => toast.error(errorText(e, locale)) });
  const probe = useMutation({ mutationFn: () => api<{ capabilities: Record<string, unknown> }>("/ai/probe", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-config"] }), onError: (e) => toast.error(errorText(e, locale)) });
  const c = q.data;
  if (!c) return <SkeletonRows />;
  const caps = (probe.data?.capabilities ?? c.active.capabilities) as Record<string, unknown>;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel title={t.gov.activeModel} actions={c.active.is_mock && <Badge>{t.demo.mock}</Badge>}>
        <DescList items={[{ label: t.settings.provider, value: <span className="ltr">{c.active.provider}</span> }, { label: t.settings.model, value: <span className="ltr">{c.active.model}</span> },
          { label: t.settings.baseUrl, value: <span className="ltr">{c.active.base_url || "—"}</span> }, { label: t.settings.apiKey, value: c.active.api_key_configured ? t.settings.configured : t.settings.notConfigured },
          { label: t.kb.embedding, value: <span className="ltr">{c.embedding.provider} / {c.embedding.model} ({c.embedding.dim}d)</span> }, { label: t.kb.vectorBackend, value: <span className="ltr">{c.vector_backend}</span> }]} />
        <div className="mt-5 border-t border-line pt-4">
          <p className="mb-2 text-[12.5px] text-muted">{t.gov.capabilities}</p>
          <div className="flex flex-wrap gap-1.5">{Object.entries(caps).filter(([, v]) => typeof v === "boolean").map(([k, v]) => (
            <span key={k} className={`ltr rounded px-2 py-0.5 text-[12px] ${v ? "bg-success-soft text-success" : "bg-surface-2 text-faint line-through"}`}>{k}</span>))}</div>
          {Array.isArray(caps.notes) && <ul className="mt-2 text-[12px] text-muted">{(caps.notes as string[]).map((n) => <li key={n} dir="ltr" className="text-start">{n}</li>)}</ul>}
          {can("governance:manage") && <Button className="mt-4" size="sm" variant="secondary" loading={probe.isPending} onClick={() => probe.mutate()}><Radar />{t.gov.probe}</Button>}
          <p className="mt-2 text-[12px] text-muted">{t.gov.probeHint}</p>
        </div>
      </Panel>
      <Panel title={t.gov.switchModel}>
        <Table>
          <thead><tr><Th>{t.settings.provider}</Th><Th>{t.settings.baseUrl}</Th><Th>{t.settings.apiKey}</Th><Th>{t.settings.model}</Th></tr></thead>
          <tbody>{Object.entries(c.providers).map(([p, v]) => (
            <Tr key={p}><Td className="ltr text-start">{p}</Td><Td><Badge tone={v.base_url_configured ? "success" : "neutral"}>{v.base_url_configured ? t.settings.configured : t.settings.notConfigured}</Badge></Td>
              <Td><Badge tone={v.api_key_configured ? "success" : "neutral"}>{v.api_key_configured ? t.settings.configured : t.settings.notConfigured}</Badge></Td><Td className="ltr text-start text-[12px] text-muted">{v.default_model || "—"}</Td></Tr>))}
          </tbody>
        </Table>
        {can("governance:manage") && (
          <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_1.4fr_auto] sm:items-end">
            <Field label={t.settings.provider}><Select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="">{pick("اختر…", "Choose…")}</option>{["mock", "qwen", "llama", "openai_compatible"].map((p) => <option key={p} value={p}>{p}</option>)}</Select></Field>
            <Field label={t.settings.model}><Input dir="ltr" value={model} placeholder={c.providers[provider]?.default_model} onChange={(e) => setModel(e.target.value)} /></Field>
            <Button disabled={!provider} loading={switchM.isPending} onClick={() => switchM.mutate()}>{t.gov.switchModel}</Button>
          </div>
        )}
        <Notice className="mt-4">{t.settings.envNote}</Notice>
      </Panel>
    </div>
  );
}

function SystemTab() {
  const { t, fmtNum } = useI18n();
  const q = useQuery({ queryKey: ["sys-settings"], queryFn: () => api<{ runtime: Record<string, number | string>; settings: { key: string; value: unknown; scope: string }[] }>("/system/settings") });
  if (!q.data) return <SkeletonRows />;
  return (
    <Panel title={t.settings.runtime}>
      <DescList cols={3} items={Object.entries(q.data.runtime).map(([k, v]) => ({ label: k.replaceAll("_", " "), value: <span className="ltr num">{typeof v === "number" ? fmtNum(v) : v}</span> }))} />
    </Panel>
  );
}
