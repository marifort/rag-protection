export type ToolPolicyDefaults = {
  challenge_threshold?: number;
  block_threshold?: number;
  challenge_mode?: string;
};

export type ToolPolicyEntryView = {
  name?: string;
  description?: string;
  backend?: string;
  allowed_groups?: string[];
  max_args_bytes?: number;
  blocked_patterns?: string[];
  blocked_domains?: string[];
  scan_arguments?: string[];
  mcp_tool?: string;
  description_blocked?: boolean;
  description_findings_count?: number;
};

export type ToolPolicyResponse = {
  source_path?: string | null;
  tool_count?: number;
  defaults?: ToolPolicyDefaults;
  tools?: Record<string, ToolPolicyEntryView>;
};
