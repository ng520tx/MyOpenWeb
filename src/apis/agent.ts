import type { AgentRun } from '@/types';

export async function fetchAgentRun(runId: string): Promise<AgentRun> {
  const res = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}`);
  if (!res.ok) {
    throw new Error(`Agent run request failed: HTTP ${res.status}`);
  }
  return (await res.json()) as AgentRun;
}
