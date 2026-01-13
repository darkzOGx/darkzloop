/**
 * darkzloop TypeScript Type Definitions
 * 
 * Use these types when integrating darkzloop with TypeScript/JavaScript agents.
 * These mirror the Python schemas in core/schemas.py.
 */

// =============================================================================
// Enums
// =============================================================================

export type ActionType = 
  | 'read_file'
  | 'write_file'
  | 'modify_file'
  | 'run_command'
  | 'search_code'
  | 'ask_human'
  | 'commit'
  | 'no_op';

export type TaskStatus = 
  | 'pending'
  | 'in_progress'
  | 'complete'
  | 'failed'
  | 'blocked'
  | 'skipped';

export type LoopState = 
  | 'init'
  | 'plan'
  | 'execute'
  | 'observe'
  | 'critique'
  | 'checkpoint'
  | 'complete'
  | 'failed'
  | 'blocked';

export type CritiqueVerdict = 
  | 'proceed'
  | 'retry'
  | 'escalate'
  | 'abort';

// =============================================================================
// Input Types (Agent receives these)
// =============================================================================

export interface TaskDefinition {
  id: string;
  description: string;
  files_to_modify: string[];
  files_to_create: string[];
  reference_files: string[];
  spec_sections: string[];
  acceptance_criteria: string;
  dependencies?: string[];
}

export interface LoopInput {
  task: TaskDefinition;
  fsm_state: LoopState;
  valid_actions: LoopState[];
  iteration: number;
  history_summary: string;
  goal_reminder: string;
}

// =============================================================================
// Output Types (Agent produces these)
// =============================================================================

export interface AgentAction {
  action: ActionType;
  target: string;
  content?: string;
  reason?: string;
}

export interface ExecutionResult {
  action: AgentAction;
  success: boolean;
  output: string;
  error?: string;
  duration_ms?: number;
}

export interface Observation {
  execution_succeeded: boolean;
  tests_passed: boolean;
  files_changed: string[];
  issues_found: string[];
  next_step_suggestion: string;
  confidence: number; // 0.0 to 1.0
}

export interface CritiqueResult {
  matches_spec: boolean;
  matches_goal: boolean;
  issues: string[];
  should_retry: boolean;
  should_proceed: boolean;
  reasoning: string;
}

export interface CheckpointData {
  iteration: number;
  task_id: string;
  task_status: TaskStatus;
  commit_hash?: string;
  summary: string;
  timestamp?: string;
}

// =============================================================================
// FSM Types
// =============================================================================

export interface StateTransition {
  from: LoopState;
  to: LoopState;
  timestamp: string;
  reason: string;
  iteration: number;
}

export interface FSMState {
  current_state: LoopState;
  iteration: number;
  consecutive_failures: number;
  transitions: StateTransition[];
}

// Valid state transitions
export const VALID_TRANSITIONS: Record<LoopState, LoopState[]> = {
  init: ['plan', 'failed'],
  plan: ['execute', 'blocked', 'failed'],
  execute: ['observe', 'failed'],
  observe: ['critique', 'failed'],
  critique: ['checkpoint', 'execute', 'failed'],
  checkpoint: ['plan', 'complete'],
  complete: [],
  failed: ['plan'],
  blocked: ['plan', 'failed'],
};

// =============================================================================
// DAG Types
// =============================================================================

export type NodeStatus = 
  | 'pending'
  | 'ready'
  | 'running'
  | 'complete'
  | 'failed'
  | 'skipped';

export interface DAGNode {
  id: string;
  task_data: TaskDefinition;
  dependencies: string[];
  status: NodeStatus;
  result?: unknown;
  error?: string;
  duration_ms?: number;
}

export interface DAGExecutionResult {
  success: boolean;
  completed_nodes: string[];
  failed_nodes: string[];
  skipped_nodes: string[];
  total_duration_ms: number;
  parallel_groups: string[][];
}

// =============================================================================
// Context Types
// =============================================================================

export interface IterationSummary {
  iteration: number;
  task_id: string;
  outcome: 'success' | 'failure' | 'partial';
  key_changes: string[];
  commit_hash?: string;
  one_liner: string;
}

export interface ContextState {
  goal: string;
  spec_excerpt: string;
  summaries: IterationSummary[];
  mermaid_state: string;
}

// =============================================================================
// Validation Helpers
// =============================================================================

export function isValidAction(action: AgentAction): { valid: boolean; error?: string } {
  const validTypes: ActionType[] = [
    'read_file', 'write_file', 'modify_file', 
    'run_command', 'search_code', 'ask_human', 'commit', 'no_op'
  ];
  
  if (!validTypes.includes(action.action)) {
    return { valid: false, error: `Invalid action type: ${action.action}` };
  }
  
  if (!action.target) {
    return { valid: false, error: 'Action requires a target' };
  }
  
  if (['write_file', 'modify_file'].includes(action.action) && !action.content) {
    return { valid: false, error: `${action.action} requires content` };
  }
  
  return { valid: true };
}

export function canTransition(from: LoopState, to: LoopState): boolean {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

export function getValidTransitions(state: LoopState): LoopState[] {
  return VALID_TRANSITIONS[state] ?? [];
}

// =============================================================================
// Compact Serialization
// =============================================================================

export function toCompactSummary(summary: IterationSummary): string {
  const changes = summary.key_changes.slice(0, 3).join(',');
  return `[i${summary.iteration}] ${summary.task_id}: ${summary.outcome} | ${changes} | ${summary.one_liner.slice(0, 50)}`;
}

export function toFSMCompact(fsm: FSMState): string {
  const valid = getValidTransitions(fsm.current_state);
  return `[FSM] state=${fsm.current_state} iter=${fsm.iteration} fails=${fsm.consecutive_failures} valid_next=[${valid.join(',')}]`;
}
