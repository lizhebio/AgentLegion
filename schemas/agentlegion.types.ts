export type RuntimeClass =
  | "deepagents"
  | "openclaw"
  | "claude-code"
  | "hermes"
  | "open-webui-chat"
  | (string & {});

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type AgentUnit = {
  apiVersion: "agentlegion.dev/v0";
  kind: "AgentUnit";
  metadata: {
    id: string;
    name?: string;
    description: string;
    labels?: Record<string, string>;
  };
  runtime: {
    class: RuntimeClass;
    adapter: string;
    nativeRef?: string;
    version?: string;
  };
  capabilities: CapabilityProfile;
  interfaces: AgentInterfaces;
  limits?: AgentLimits;
  safety: SafetyProfile;
  extensions?: Record<string, unknown>;
};

export type CapabilityProfile = {
  domains: string[];
  actions: {
    readFiles?: boolean;
    writeFiles?: boolean;
    runShell?: boolean;
    useMcp?: boolean;
    browseWeb?: boolean;
    sendMessages?: boolean;
    spawnSubagents?: boolean;
    scheduleTasks?: boolean;
    bindChannels?: boolean;
    useSecrets?: boolean;
    producePatch?: boolean;
    reviewCode?: boolean;
    performResearch?: boolean;
  };
  strengths?: string[];
  weaknesses?: string[];
  state?: {
    resume?: "none" | "runtime-local" | "portable";
    memory?: "none" | "runtime-local" | "external";
    checkpoint?: "none" | "runtime-local" | "portable";
  };
  sideEffects?: Array<
    | "filesystem.write"
    | "shell.execute"
    | "network.egress"
    | "mcp.install"
    | "secret.read"
    | "channel.send"
    | "schedule.create"
    | "subagent.spawn"
    | (string & {})
  >;
};

export type AgentInterfaces = {
  input: Array<"task_brief" | "messages" | "file_paths" | "diff" | "repo_context" | "artifacts" | (string & {})>;
  output: Array<"findings" | "plan" | "patch" | "review" | "report" | "decision" | "artifacts" | (string & {})>;
  eventModes?: Array<"stream" | "poll" | "callback" | "webhook">;
};

export type AgentLimits = {
  maxConcurrentTasks?: number;
  timeoutSeconds?: number;
  maxTurns?: number;
  maxCostUsd?: number;
};

export type SafetyProfile = {
  trustLevel: RiskLevel;
  defaultPolicy?: "allow" | "deny" | "ask";
  requiresApprovalFor?: string[];
  sandboxRequired?: boolean;
  auditLevel?: "minimal" | "standard" | "raw";
};

export type LegionPlan = {
  apiVersion: "agentlegion.dev/v0";
  kind: "LegionPlan";
  metadata: {
    name: string;
    description?: string;
  };
  units: string[];
  roles: Record<string, string | string[]>;
  routing?: RoutingRule[];
  policies?: string[];
  limits?: {
    maxParallelTasks?: number;
    maxActiveMissions?: number;
  };
};

export type RoutingRule = {
  match: {
    domains?: string[];
    actions?: string[];
    inputTypes?: string[];
    outputTypes?: string[];
    riskMax?: RiskLevel;
  };
  prefer?: string[];
  deny?: string[];
};

export type MissionSpec = {
  apiVersion: "agentlegion.dev/v0";
  kind: "MissionSpec";
  metadata: {
    id: string;
    name?: string;
    description?: string;
  };
  goal: string;
  context?: {
    workspace?: string;
    files?: string[];
    artifacts?: string[];
    variables?: Record<string, unknown>;
  };
  constraints?: {
    timeoutSeconds?: number;
    maxCostUsd?: number;
    requireApprovalBeforeSideEffects?: boolean;
  };
  workflow?: MissionStep[];
  expectedOutput?: {
    type: string;
    schema?: Record<string, unknown>;
  };
};

export type MissionStep = {
  id: string;
  task: string;
  role?: string;
  agentId?: string;
  dependsOn?: string[];
  inputArtifacts?: string[];
  expectedOutput: string;
  requiresApproval?: boolean;
  constraints?: MissionSpec["constraints"];
};

export type PolicySpec = {
  apiVersion: "agentlegion.dev/v0";
  kind: "PolicySpec";
  metadata: {
    name: string;
    description?: string;
  };
  defaults: {
    effect: "allow" | "deny" | "ask";
  };
  rules: PolicyRule[];
};

export type PolicyRule = {
  id: string;
  resource: string;
  action?: string;
  effect: "allow" | "deny" | "ask";
  match?: Record<string, unknown>;
  appliesTo?: {
    agents?: string[];
    roles?: string[];
    missions?: string[];
  };
};

export type AgentTask = {
  id: string;
  missionId: string;
  goal: string;
  inputs?: {
    messages?: Message[];
    files?: string[];
    diff?: string;
    artifacts?: ArtifactRef[];
    context?: Record<string, unknown>;
  };
  constraints?: {
    maxTurns?: number;
    timeoutSeconds?: number;
    allowedTools?: string[];
    deniedTools?: string[];
    requireApproval?: boolean;
  };
  expectedOutput: {
    format: "summary" | "findings" | "patch" | "json" | "artifact" | string;
    schema?: Record<string, unknown>;
  };
};

export type Message = {
  role: "system" | "user" | "assistant" | "tool";
  content: unknown;
};

export type ArtifactRef = {
  id: string;
  type: Artifact["type"];
};

export type Artifact = {
  id: string;
  type: "finding" | "evidence_bundle" | "plan" | "patch" | "review" | "report" | "decision" | "run_log" | string;
  producedBy: string;
  missionId: string;
  taskId?: string;
  contentRef: string;
  evidence?: SourceRef[];
  status?: "draft" | "final" | "rejected" | "superseded";
  createdAt: string;
};

export type SourceRef = {
  uri: string;
  line?: number;
  symbol?: string;
  quote?: string;
};

export type RuntimePlan = {
  id: string;
  runtimeClass: RuntimeClass;
  agentUnitId: string;
  missionId: string;
  taskId: string;
  adapterVersion?: string;
  nativeConfig: unknown;
  exposedTools?: string[];
  permissionPlan?: unknown;
  sandboxPlan?: unknown;
  expectedArtifacts?: string[];
  approvalPoints?: string[];
  warnings?: string[];
  unsupported?: string[];
};

export type RuntimeHandle = {
  id: string;
  runtimeClass: RuntimeClass;
  agentUnitId: string;
  missionId: string;
  taskId: string;
  sessionId?: string;
  runId?: string;
  nativeRef?: unknown;
  phase: RuntimeStatus["phase"];
};

export type RuntimeStatus = {
  phase:
    | "planned"
    | "running"
    | "pending_approval"
    | "suspended"
    | "completed"
    | "failed"
    | "cancelled";
  message?: string;
  lastEventAt?: string;
};

export type AgentEvent = {
  type:
    | "started"
    | "message"
    | "tool_call"
    | "tool_result"
    | "approval_required"
    | "approval_result"
    | "artifact"
    | "checkpoint"
    | "completed"
    | "failed"
    | "cancelled"
    | "raw";
  agentId: string;
  missionId: string;
  taskId: string;
  timestamp: string;
  data?: unknown;
  raw?: unknown;
};

export type ValidationResult = {
  ok: boolean;
  diagnostics: Array<{
    level: "error" | "warning" | "info";
    message: string;
    field?: string;
  }>;
};

export type RuntimeCapabilities = {
  runtimeClass: RuntimeClass;
  inputTypes: string[];
  outputTypes: string[];
  eventTypes: string[];
  supportsCancel: boolean;
  supportsApproval: boolean;
  supportsResume: boolean;
  supportsSandbox: boolean;
  supportsRawEvents: boolean;
};

export type ApprovalDecision = {
  approvalId: string;
  decision: "allow" | "deny";
  reason?: string;
  modifiedInput?: unknown;
};

export type RuntimeStateSnapshot = {
  runtimeClass: RuntimeClass;
  sessionId?: string;
  checkpointId?: string;
  native: unknown;
};

export type TrajectoryStatus = "running" | "completed" | "failed" | "cancelled" | "replayed";

export type StepStatus = "started" | "completed" | "failed" | "skipped" | "retrying";

export type StepType =
  | "message"
  | "llm_call"
  | "tool_call"
  | "retrieval"
  | "state_transition"
  | "artifact"
  | "approval"
  | "subagent"
  | "workflow"
  | (string & {});

export type ContentRef = {
  uri: string;
  mediaType?: string;
  hash?: string;
  sizeBytes?: number;
};

export type TrajectoryRun = {
  apiVersion: "agentlegion.dev/v0";
  kind: "TrajectoryRun";
  trajectoryId: string;
  traceId?: string;
  sessionId: string;
  missionId?: string;
  taskId?: string;
  agentUnitId: string;
  runtimeClass: RuntimeClass;
  agentVersion: string;
  promptVersion?: string;
  model?: string;
  modelParamsRef?: ContentRef;
  toolSchemaVersion?: string;
  taskType: string;
  status: TrajectoryStatus;
  finalOutcome?: "success" | "failure" | "partial" | "unknown";
  cost?: {
    totalUsd?: number;
    inputTokens?: number;
    outputTokens?: number;
  };
  latencyMs?: number;
  normalizerVersion: string;
  startedAt: string;
  endedAt?: string;
  rawTraceRef?: ContentRef;
  metadata?: Record<string, unknown>;
};

export type TrajectoryStep = {
  apiVersion: "agentlegion.dev/v0";
  kind: "TrajectoryStep";
  stepId: string;
  trajectoryId: string;
  parentStepId?: string;
  stepIndex: number;
  turnIndex?: number;
  stepType: StepType;
  name?: string;
  status: StepStatus;
  inputRef?: ContentRef;
  outputRef?: ContentRef;
  startedAt?: string;
  endedAt?: string;
  latencyMs?: number;
  errorType?: string;
};

export type MessageEvent = {
  apiVersion: "agentlegion.dev/v0";
  kind: "MessageEvent";
  messageId: string;
  stepId: string;
  trajectoryId: string;
  role: Message["role"];
  contentRef: ContentRef;
  contentType: "text" | "json" | "image" | "audio" | "tool_result" | (string & {});
  tokenCount?: number;
  toolCallId?: string;
  timestamp: string;
};

export type LLMCallFact = {
  apiVersion: "agentlegion.dev/v0";
  kind: "LLMCallFact";
  stepId: string;
  trajectoryId: string;
  provider: string;
  model: string;
  paramsRef?: ContentRef;
  promptRef?: ContentRef;
  completionRef?: ContentRef;
  inputTokens?: number;
  outputTokens?: number;
  costUsd?: number;
  finishReason?: string;
  latencyMs?: number;
};

export type SideEffectType =
  | "read_only"
  | "write_internal"
  | "write_external"
  | "user_visible_publish"
  | "payment_or_financial"
  | "permission_change"
  | "irreversible";

export type ApprovalStatus = "not_required" | "pending" | "approved" | "denied" | "expired" | "unknown";

export type ToolCallFact = {
  apiVersion: "agentlegion.dev/v0";
  kind: "ToolCallFact";
  toolCallId: string;
  stepId: string;
  trajectoryId: string;
  toolName: string;
  namespace: string;
  args?: unknown;
  argsHash: string;
  argsRef?: ContentRef;
  validationResult?: ValidationResult;
  result?: unknown;
  resultRef?: ContentRef;
  resultSummary?: string;
  isError: boolean;
  errorType?: string;
  latencyMs?: number;
  retryIndex: number;
  sideEffectType: SideEffectType;
  approvalStatus: ApprovalStatus;
  sourceStepId?: string;
};

export type RetrievalFact = {
  apiVersion: "agentlegion.dev/v0";
  kind: "RetrievalFact";
  stepId: string;
  trajectoryId: string;
  retrieverName: string;
  queryRef: ContentRef;
  topK?: number;
  documentIds?: string[];
  scores?: number[];
  corpusVersion?: string;
};

export type StateTransitionFact = {
  apiVersion: "agentlegion.dev/v0";
  kind: "StateTransitionFact";
  stepId: string;
  trajectoryId: string;
  stateName: string;
  fromStateRef?: ContentRef;
  toStateRef?: ContentRef;
  deltaRef?: ContentRef;
  reasonRef?: ContentRef;
};

export type ArtifactFact = {
  apiVersion: "agentlegion.dev/v0";
  kind: "ArtifactFact";
  artifactId: string;
  stepId: string;
  trajectoryId: string;
  artifactType: Artifact["type"];
  uri: string;
  metadataRef?: ContentRef;
  qualityStatus?: "unchecked" | "pass" | "warn" | "fail";
};

export type ScoreFact = {
  apiVersion: "agentlegion.dev/v0";
  kind: "ScoreFact";
  scoreId: string;
  trajectoryId?: string;
  targetType: "trajectory_run" | "trajectory_step" | "tool_call" | "artifact" | "regression_case" | string;
  targetId: string;
  scoreName: string;
  scoreType: "binary" | "numeric" | "categorical" | "rubric" | "human_feedback" | string;
  scoreValue: number | string | boolean;
  evaluatorType: "human" | "llm" | "rule" | "unit_test" | "integration_test" | string;
  evaluatorVersion?: string;
  rationaleRef?: ContentRef;
  createdAt: string;
};

export type RootCauseCategory =
  | "Intent"
  | "Planning"
  | "Tool Selection"
  | "Tool Arguments"
  | "Observation Use"
  | "Retrieval"
  | "State"
  | "Recovery"
  | "Artifact"
  | "Policy / Safety"
  | "Infrastructure"
  | "Evaluation";

export type RegressionCase = {
  apiVersion: "agentlegion.dev/v0";
  kind: "RegressionCase";
  caseId: string;
  sourceTrajectoryId: string;
  rootCauseCategory: RootCauseCategory;
  rootCauseDetail?: string;
  failedStepId?: string;
  severity: RiskLevel;
  fixOwner?: string;
  regressionPriority: "P0" | "P1" | "P2";
  replayInputRef: ContentRef;
  expectedBehaviorRef: ContentRef;
  replaySnapshotRef?: ContentRef;
  createdFromFailureAt: string;
  status: "active" | "fixed" | "quarantined" | "retired";
};

export type ReplaySnapshot = {
  apiVersion: "agentlegion.dev/v0";
  kind: "ReplaySnapshot";
  snapshotId: string;
  regressionCaseId?: string;
  trajectoryId?: string;
  userInputRef: ContentRef;
  initialStateRef?: ContentRef;
  memorySnapshotRef?: ContentRef;
  toolSpaceSnapshotRef?: ContentRef;
  toolSchemaSnapshotRef?: ContentRef;
  retrievalCorpusVersion?: string;
  permissionContextRef?: ContentRef;
  externalApiFixtureRef?: ContentRef;
  clock: {
    instant: string;
    timezone: string;
  };
  featureFlags?: Record<string, boolean | string | number>;
  modelConfigRef?: ContentRef;
  promptVersion?: string;
  expectedBehaviorRef: ContentRef;
};

export type TrajectoryDiff = {
  apiVersion: "agentlegion.dev/v0";
  kind: "TrajectoryDiff";
  diffId: string;
  baselineTrajectoryId: string;
  candidateTrajectoryId: string;
  changedStepIds?: string[];
  addedStepIds?: string[];
  removedStepIds?: string[];
  behaviorChanges?: Array<{
    category: "final_outcome" | "tool_selection" | "tool_arguments" | "observation_use" | "latency" | "cost" | string;
    severity: RiskLevel;
    summary: string;
    evidenceRef?: ContentRef;
  }>;
  createdAt: string;
};

export type ReleaseGate = {
  apiVersion: "agentlegion.dev/v0";
  kind: "ReleaseGate";
  gateId: string;
  targetVersion: string;
  regressionSuiteRef?: ContentRef;
  thresholds: {
    severeRootCauseRecurrence: number;
    maxCostIncreaseRatio?: number;
    maxLatencyP95IncreaseRatio?: number;
    minPassRate?: number;
  };
  status: "pass" | "fail" | "warning" | "pending";
  scoreRefs?: ContentRef[];
  trajectoryDiffRefs?: ContentRef[];
  decidedAt?: string;
};

export type NormalizedTrajectoryBatch = {
  trajectoryRun?: TrajectoryRun;
  steps: TrajectoryStep[];
  messages: MessageEvent[];
  llmCalls: LLMCallFact[];
  toolCalls: ToolCallFact[];
  retrievals: RetrievalFact[];
  stateTransitions: StateTransitionFact[];
  artifacts: ArtifactFact[];
  scores: ScoreFact[];
  rawEventRefs: ContentRef[];
  diagnostics: ValidationResult["diagnostics"];
};

export interface TrajectoryStore {
  init(): Promise<void> | void;

  writeRawEvent(input: {
    trajectoryId: string;
    eventIndex: number;
    event: AgentEvent;
  }): Promise<ContentRef> | ContentRef;

  writeFact(
    fact:
      | TrajectoryRun
      | TrajectoryStep
      | MessageEvent
      | LLMCallFact
      | ToolCallFact
      | RetrievalFact
      | StateTransitionFact
      | ArtifactFact
      | ScoreFact
      | RegressionCase
      | ReplaySnapshot
      | TrajectoryDiff
      | ReleaseGate
  ): Promise<ContentRef> | ContentRef;

  readTrajectory?(trajectoryId: string): Promise<NormalizedTrajectoryBatch>;
}

export interface EventNormalizer {
  readonly version: string;

  normalize(input: {
    trajectoryId: string;
    sessionId: string;
    agentVersion: string;
    taskType: string;
    events: AgentEvent[];
  }): Promise<NormalizedTrajectoryBatch> | NormalizedTrajectoryBatch;
}

export interface RuntimeAdapter {
  readonly runtimeClass: RuntimeClass;

  capabilities(): Promise<RuntimeCapabilities> | RuntimeCapabilities;

  validateUnit(unit: AgentUnit): Promise<ValidationResult> | ValidationResult;

  validateTask(unit: AgentUnit, task: AgentTask): Promise<ValidationResult> | ValidationResult;

  plan(input: {
    unit: AgentUnit;
    task: AgentTask;
    policy: PolicySpec;
    context?: Record<string, unknown>;
  }): Promise<RuntimePlan> | RuntimePlan;

  invoke(plan: RuntimePlan): AsyncIterable<AgentEvent>;

  status?(handle: RuntimeHandle): Promise<RuntimeStatus>;

  cancel?(handle: RuntimeHandle, reason?: string): Promise<void>;

  approve?(handle: RuntimeHandle, decision: ApprovalDecision): Promise<void>;

  exportState?(handle: RuntimeHandle): Promise<RuntimeStateSnapshot>;

  normalizeEvent?(raw: unknown): AgentEvent;
}
