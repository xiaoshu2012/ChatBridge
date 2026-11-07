// Isolated M1 fixture only. Never mount this bundle in a user's real Harness home.
import { appendFileSync, realpathSync } from 'node:fs';
import { setSandboxMode } from '@deepseek-ai/dsh-sandbox-policy';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';

export const name = 'chatbridge-m1-native-probe';
export const inject = ['sandboxPolicy', 'approval', 'userQuestions'];

export function apply(ctx) {
  const phase = process.env.CHATBRIDGE_NATIVE_PHASE;
  if (!['seed', 'guard', 'reject', 'question'].includes(phase)) {
    throw new Error('CHATBRIDGE_NATIVE_INVALID_PHASE');
  }
  const record = value => appendFileSync(
    process.env.CHATBRIDGE_NATIVE_TRACE, JSON.stringify({ phase, ...value }) + '\n');
  const expectedWorkspace = realpathSync(process.env.CHATBRIDGE_NATIVE_WORKSPACE);
  ctx.on('agent/created', ({ agent, source }) => {
    const session = agent.session;
    const before = {
      sandbox: ctx.sandboxPolicy.resolve({ session }).mode,
      approval: ctx.approval.effectivePolicy(session),
    };
    if (phase === 'reject') {
      record({ event: 'rejected', source });
      throw new Error('CHATBRIDGE_POLICY_GUARD_REJECTED');
    }
    const workspaceMatch = realpathSync(session.header.cwd) === expectedWorkspace;
    if (!workspaceMatch) throw new Error('CHATBRIDGE_NATIVE_WORKSPACE_MISMATCH');
    // Seed a historical permission override using public native APIs only.
    // No prompt, model, tool execution or user session is used in any phase.
    setSandboxMode(session, phase === 'seed' ? 'danger-full-access' : 'workspace-write');
    setApprovalPolicy(session, phase === 'seed' ? 'ask' : 'never');
    const after = {
      sandbox: ctx.sandboxPolicy.resolve({ session }).mode,
      approval: ctx.approval.effectivePolicy(session),
    };
    if (after.sandbox !== (phase === 'seed' ? 'danger-full-access' : 'workspace-write') ||
        after.approval !== (phase === 'seed' ? 'ask' : 'never')) {
      throw new Error('CHATBRIDGE_NATIVE_POLICY_READBACK_FAILED');
    }
    record({ event: 'policy', source, before, after, workspaceMatch });
    if (phase === 'question') {
      setTimeout(async () => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 4000);
        try {
          const result = await ctx.userQuestions.ask({
            agent, signal: controller.signal,
            questions: [{ id: 'm1-question', question: 'Controlled SDK probe', options: [{ label: 'Probe answer' }] }],
          });
          record({ event: 'question-result', matched:
            result.answers.length === 1 && result.answers[0].id === 'm1-question' &&
            result.answers[0].selected.length === 1 && result.answers[0].selected[0] === 'Probe answer' });
        } catch (error) {
          // Retain an allowlisted diagnostic code, never native error text.
          const code = ['NO_PROVIDER', 'ASK_ABORTED', 'BAD_ANSWER'].includes(error.code) ? error.code : 'UNKNOWN';
          record({ event: 'question-error', code });
        } finally {
          clearTimeout(timeout);
        }
      }, 50);
    }
  });
  // Explicit marker after registration: successful SDK initialization alone is insufficient.
  record({ event: 'plugin-ready' });
}
