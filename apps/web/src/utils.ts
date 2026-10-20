import type { Claim, ClaimStatus, ClaimType } from "./types";

export const claimTypeLabel: Record<ClaimType, string> = {
  fact: "事实",
  opinion: "观点",
  speculation: "推测",
  rumor: "传闻",
  denial: "否认",
  correction: "更正",
};

export const claimTypeClass: Record<ClaimType, string> = {
  fact: "fact",
  opinion: "opinion",
  speculation: "speculation",
  rumor: "rumor",
  denial: "denial",
  correction: "correction",
};

export const statusLabel: Record<ClaimStatus, string> = {
  active: "有效",
  denied: "已被否认",
  unverified: "未核实",
  superseded: "已被替代",
};

export const sourceTierLabel: Record<string, string> = {
  exchange: "交易所",
  company_official: "公司官方",
  media: "财经媒体",
  research: "研报",
  anonymous: "匿名传闻",
};

export const docTypeLabel: Record<string, string> = {
  announcement: "公告",
  clarification: "澄清公告",
  news: "新闻",
  research: "研报",
};

export function formatDate(value: string | null | undefined): string {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(date)
    .replace(/\//g, "-");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(date)
    .replace(/\//g, "-");
}

export function strengthBandLabel(band: string): string {
  if (band === "strong") return "强";
  if (band === "medium") return "中";
  return "弱";
}

export function statusDetailChips(detail: Record<string, string>): Array<{
  label: string;
  tone: string;
}> {
  const chips: Array<{ label: string; tone: string }> = [];
  if (detail?.core === "confirmed") chips.push({ label: "收购已确认", tone: "green" });
  if (detail?.core === "unverified") chips.push({ label: "核心事实待核实", tone: "amber" });
  if (detail?.core === "denied") chips.push({ label: "核心事实被否认", tone: "red" });
  if (detail?.narrative === "unverified") chips.push({ label: "传闻待核实", tone: "amber" });
  if (detail?.narrative === "denied") chips.push({ label: "传闻已否认", tone: "red" });
  if (detail?.market === "observed") chips.push({ label: "市场已反应", tone: "blue" });
  if (detail?.market === "unverified") chips.push({ label: "市场未验证", tone: "gray" });
  return chips;
}

export function claimMatchesFilter(claim: Claim, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "market") return claim.claim_role === "market_reaction";
  if (filter === "fact") return claim.claim_type === "fact" && claim.claim_role !== "market_reaction";
  return claim.claim_type === filter;
}

export function shortClaim(text: string, max = 46): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

