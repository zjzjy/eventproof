import type {
  Diff,
  EventDetail,
  EventSummary,
  Meta,
  Notification,
} from "./types";

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  events: () => getJSON<{ items: EventSummary[] }>("/events"),
  event: (id: string, asOf?: string | null) =>
    getJSON<EventDetail>(
      `/events/${encodeURIComponent(id)}${
        asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""
      }`,
    ),
  diff: (id: string, fromVersion: number, toVersion: number) =>
    getJSON<Diff>(
      `/events/${encodeURIComponent(id)}/diff?from_version=${fromVersion}&to_version=${toVersion}`,
    ),
  notifications: () =>
    getJSON<{ items: Notification[]; unread: number }>("/notifications"),
  markRead: (id: string) =>
    fetch(`/api/notifications/${encodeURIComponent(id)}/read`, {
      method: "POST",
    }).then((response) => response.json()),
  meta: () => getJSON<Meta>("/meta"),
  exportUrl: (id: string) => `/api/events/${encodeURIComponent(id)}/export`,
};

