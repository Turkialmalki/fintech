"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Lock, Play, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, Dialog, Drawer } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, Notice, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader, Panel, TabPanel, Tabs } from "@/components/ui/layout";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

type Tool = { name: string; description: string; permission: string; write: boolean; input_schema: { properties: Record<string, any>; required?: string[] }; allowed_for_you: boolean };
type Health = { tools: number; agent_transport: string; standalone_server: { url: string; reachable: boolean; detail?: unknown } };
type Exec = { id: string; tool: string; action: string; outcome: string; actor_type: string; transport: string | null; duration_ms: number | null; created_at: string; error: string | null };
type Key = { id: string; name: string; key_prefix: string; scopes: string[]; created_at: string; revoked_at: string | null; last_used_at: string | null; user_email: string };

const SAMPLE: Record<string, Record<string, unknown>> = {
  search_regulations: { query: "متطلبات رأس المال المدفوع", top_k: 3 }, get_regulation_details: { document_code: "RIP-SYN-001" },
};

export default function Integrations() {
  const { t, fmtDate, fmtNum, pick, label } = useI18n();
  const { can } = useAuth();
  const [tab, setTab] = useState("registry");
  const [testTool, setTestTool] = useState<Tool | null>(null);
  const tools = useQuery({ queryKey: ["mcp-tools"], queryFn: () => api<Tool[]>("/mcp/tools") });
  const health = useQuery({ queryKey: ["mcp-health"], queryFn: () => api<Health>("/mcp/health") });
  const execs = useQuery({ queryKey: ["mcp-execs"], queryFn: () => api<Exec[]>("/mcp/executions"), enabled: tab === "executions" });

  return (
    <div>
      <PageHeader title={t.mcp.title} subtitle={t.mcp.subtitle}
        meta={health.data && <>
          <Badge tone={health.data.standalone_server.reachable ? "success" : "neutral"} dot>{t.mcp.server}: {health.data.standalone_server.reachable ? t.mcp.reachable : t.mcp.unreachable}</Badge>
          <span className="text-[12.5px] text-muted">{t.mcp.transport}: <span className="ltr">{health.data.agent_transport}</span></span>
          <span className="text-[12.5px] text-muted num">{fmtNum(health.data.tools)} {pick("أدوات", "tools")}</span>
        </>} />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "registry", label: t.mcp.registry }, ...(can("mcp:manage") ? [{ value: "keys", label: t.mcp.keys }] : []),
        { value: "executions", label: t.mcp.executions }, { value: "connect", label: t.mcp.connect }]}>
        <TabPanel value="registry">
          {tools.isError ? <ErrorState error={tools.error} /> : !tools.data ? <SkeletonRows /> : (
            <ul className="grid gap-3 lg:grid-cols-2">
              {tools.data.map((tool) => (
                <li key={tool.name} className="flex flex-col rounded-xl border border-line bg-surface p-5">
                  <div className="flex items-start justify-between gap-3">
                    <code className="ltr text-[14px] font-semibold text-ink">{tool.name}</code>
                    <Badge tone={tool.write ? "warning" : "success"}>{tool.write ? <><Lock className="size-3" />{t.mcp.write}</> : t.mcp.read}</Badge>
                  </div>
                  <p dir="ltr" className="mt-2 text-start text-[13px] leading-relaxed text-ink-2">{tool.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {Object.entries(tool.input_schema.properties ?? {}).map(([k]) => (
                      <code key={k} className="ltr rounded bg-surface-2 px-1.5 py-0.5 text-[11.5px]">{k}{tool.input_schema.required?.includes(k) ? "*" : ""}</code>
                    ))}
                  </div>
                  <div className="mt-auto flex items-center justify-between gap-3 border-t border-line pt-3 mt-4">
                    <span className="text-[12px] text-muted">{t.mcp.permission}: <span className="ltr">{tool.permission}</span></span>
                    {!tool.write && tool.allowed_for_you && <Button size="sm" variant="secondary" onClick={() => setTestTool(tool)}><Play />{t.mcp.test}</Button>}
                    {tool.write && <span className="text-[12px] text-muted">{t.mcp.writeNote}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </TabPanel>
        <TabPanel value="keys"><KeysTab /></TabPanel>
        <TabPanel value="executions">
          <div className="rounded-xl border border-line bg-surface">
            {!execs.data ? <SkeletonRows className="p-5" /> : execs.data.length === 0 ? <EmptyState title={t.common.emptyTitle} /> : (
              <Table>
                <thead><tr><Th>{t.mcp.tool}</Th><Th>{t.mcp.outcome}</Th><Th>{t.audit.actor}</Th><Th>{t.mcp.transport}</Th><Th className="text-end">{t.assess.duration}</Th><Th>{t.common.date}</Th></tr></thead>
                <tbody>{execs.data.map((e) => (
                  <Tr key={e.id}>
                    <Td><code className="ltr text-[12.5px]">{e.tool}</code>{e.error && <p className="ltr text-start text-[11.5px] text-danger">{e.error}</p>}</Td>
                    <Td><Badge tone={e.outcome === "SUCCESS" ? "success" : e.outcome === "DENIED" ? "danger" : "warning"}>{label("outcome", e.outcome)}</Badge></Td>
                    <Td className="text-[12.5px]">{e.actor_type}</Td><Td className="ltr text-[12.5px] text-muted">{e.transport}</Td>
                    <Td className="text-end num">{e.duration_ms != null ? `${fmtNum(e.duration_ms)} ${t.common.ms}` : "—"}</Td>
                    <Td className="whitespace-nowrap text-ink-2">{fmtDate(e.created_at, true)}</Td>
                  </Tr>))}
                </tbody>
              </Table>
            )}
          </div>
        </TabPanel>
        <TabPanel value="connect"><ConnectGuide url={health.data?.standalone_server.url} /></TabPanel>
      </Tabs>
      <TestDrawer tool={testTool} onClose={() => setTestTool(null)} />
    </div>
  );
}

function TestDrawer({ tool, onClose }: { tool: Tool | null; onClose: () => void }) {
  const { t, locale } = useI18n();
  const [args, setArgs] = useState("");
  const run = useMutation({ mutationFn: () => api<{ result: unknown; duration_ms: number }>(`/mcp/tools/${tool!.name}/test`, { body: JSON.parse(args || "{}") }) });
  return (
    <Drawer open={!!tool} onOpenChange={(o) => { if (!o) { onClose(); run.reset(); setArgs(""); } }} title={t.mcp.test} subtitle={<code className="ltr">{tool?.name}</code>} width="max-w-3xl">
      <Notice tone="info" className="mb-4">{t.mcp.testHint}</Notice>
      <Field label={t.mcp.schema}>
        <Textarea dir="ltr" rows={5} className="font-mono text-[12.5px]" value={args || JSON.stringify(SAMPLE[tool?.name ?? ""] ?? {}, null, 2)} onChange={(e) => setArgs(e.target.value)} />
      </Field>
      <div className="mt-3 flex justify-end">
        <Button loading={run.isPending} onClick={() => { if (!args) setArgs(JSON.stringify(SAMPLE[tool?.name ?? ""] ?? {})); setTimeout(() => run.mutate(), 0); }}><Play />{t.mcp.runTest}</Button>
      </div>
      {run.isError && <Notice tone="danger" className="mt-4">{errorText(run.error, locale)}</Notice>}
      {run.data && <pre dir="ltr" className="mt-4 max-h-[50vh] overflow-auto rounded-lg border border-line bg-canvas p-4 text-[11.5px] leading-relaxed scroll-thin">{JSON.stringify(run.data.result, null, 2)}</pre>}
    </Drawer>
  );
}

function KeysTab() {
  const { t, fmtDate, locale } = useI18n();
  const qc = useQueryClient();
  const keys = useQuery({ queryKey: ["mcp-keys"], queryFn: () => api<Key[]>("/mcp/keys") });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [write, setWrite] = useState(false);
  const [created, setCreated] = useState<string | null>(null);
  const [revoke, setRevoke] = useState<Key | null>(null);
  const create = useMutation({
    mutationFn: () => api<{ api_key: string }>("/mcp/keys", { body: { name, scopes: write ? ["read", "write"] : ["read"] } }),
    onSuccess: (r) => { setCreated(r.api_key); setOpen(false); setName(""); setWrite(false); qc.invalidateQueries({ queryKey: ["mcp-keys"] }); },
    onError: (e) => toast.error(errorText(e, locale)),
  });
  return (
    <div className="rounded-xl border border-line bg-surface">
      <div className="flex justify-end border-b border-line px-5 py-3"><Button size="sm" onClick={() => setOpen(true)}><Plus />{t.mcp.newKey}</Button></div>
      {!keys.data ? <SkeletonRows className="p-5" /> : keys.data.length === 0 ? <EmptyState icon={KeyRound} title={t.mcp.noKeys} /> : (
        <Table>
          <thead><tr><Th>{t.mcp.keyName}</Th><Th>{t.mcp.scopes}</Th><Th>{t.mcp.lastUsed}</Th><Th>{t.common.date}</Th><Th /></tr></thead>
          <tbody>{keys.data.map((k) => (
            <Tr key={k.id}>
              <Td><p className="font-medium">{k.name}</p><p className="ltr text-start text-[12px] text-muted">{k.key_prefix}… · {k.user_email}</p></Td>
              <Td><div className="flex gap-1">{k.scopes.map((s) => <Badge key={s} tone={s === "write" ? "warning" : "success"}>{s === "write" ? t.mcp.write : t.mcp.read}</Badge>)}</div></Td>
              <Td className="text-ink-2">{k.last_used_at ? fmtDate(k.last_used_at, true) : "—"}</Td>
              <Td className="text-ink-2">{fmtDate(k.created_at)}</Td>
              <Td className="text-end">{k.revoked_at ? <Badge>{t.mcp.revoked}</Badge> : <Button size="sm" variant="danger-ghost" onClick={() => setRevoke(k)}>{t.mcp.revoke}</Button>}</Td>
            </Tr>))}
          </tbody>
        </Table>
      )}
      <Dialog open={open} onOpenChange={setOpen} title={t.mcp.newKey} size="sm"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>{t.common.cancel}</Button><Button disabled={name.length < 2} loading={create.isPending} onClick={() => create.mutate()}>{t.common.create}</Button></>}>
        <div className="flex flex-col gap-4">
          <Field label={t.mcp.keyName} htmlFor="kn"><Input id="kn" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Checkbox label={t.mcp.allowWrite} checked={write} onChange={setWrite} />
        </div>
      </Dialog>
      <Dialog open={!!created} onOpenChange={(o) => !o && setCreated(null)} title={t.mcp.newKey} description={t.mcp.keyCreated} size="sm"
        footer={<Button onClick={() => { navigator.clipboard.writeText(created ?? ""); toast.success(t.common.copied); }}><Copy />{t.common.copy}</Button>}>
        <code className="ltr block break-all rounded-md bg-surface-2 p-3 text-[12.5px]">{created}</code>
      </Dialog>
      <ConfirmDialog open={!!revoke} onOpenChange={(o) => !o && setRevoke(null)} title={t.mcp.revoke} description={t.mcp.revokeConfirm} tone="danger" confirmLabel={t.mcp.revoke}
        onConfirm={async () => { await api(`/mcp/keys/${revoke!.id}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["mcp-keys"] }); }} />
    </div>
  );
}

function ConnectGuide({ url }: { url?: string }) {
  const { pick } = useI18n();
  const cfg = JSON.stringify({ mcpServers: { rip: { url: url ?? "http://localhost:8765/mcp", headers: { Authorization: "Bearer rip_…" } } } }, null, 2);
  const stdio = JSON.stringify({ mcpServers: { rip: { command: "python", args: ["-m", "rip_mcp", "--transport", "stdio"], env: { RIP_MCP_API_KEY: "rip_…", DATABASE_URL: "postgresql+psycopg://…" } } } }, null, 2);
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel title={pick("عبر HTTP (Streamable HTTP)", "Over HTTP (Streamable HTTP)")} description={pick("لعملاء MCP الذين يدعمون الاتصال عن بعد.", "For MCP clients that support remote servers.")}>
        <pre dir="ltr" className="overflow-auto rounded-lg border border-line bg-canvas p-4 text-[12px]">{cfg}</pre>
      </Panel>
      <Panel title={pick("عبر stdio", "Over stdio")} description={pick("لتطبيقات سطح المكتب التي تشغّل الخادم محلياً.", "For desktop apps that launch the server locally.")}>
        <pre dir="ltr" className="overflow-auto rounded-lg border border-line bg-canvas p-4 text-[12px]">{stdio}</pre>
      </Panel>
      <Notice tone="info" className="xl:col-span-2">{pick("المفاتيح للقراءة فقط افتراضياً. أدوات الكتابة (إنشاء مسودة، الإحالة للمراجعة) تتطلب مفتاحاً بصلاحية كتابة صريحة، وكل استدعاء يُسجّل في سجل العمليات. لا يوفر الخادم أي وصول عام إلى قاعدة البيانات أو الملفات أو الشبكة.",
        "Keys are read-only by default. Write tools (create draft, submit for review) require a key with an explicit write scope, and every call is audited. The server exposes no generic database, file or network access.")}</Notice>
    </div>
  );
}
