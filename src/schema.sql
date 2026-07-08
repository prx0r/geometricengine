CREATE TABLE IF NOT EXISTS mythought_hyperedges (
  id TEXT PRIMARY KEY,
  source TEXT,
  episode_id TEXT,
  turn_id TEXT,
  turn_index INTEGER,

  mythought_text TEXT,
  assistant_visible_text TEXT,
  previous_user_text TEXT,
  next_user_text TEXT,

  lineage TEXT,
  phase TEXT,
  function_id TEXT,
  mechanism_shape TEXT,
  intent TEXT,
  impact_predicted TEXT,
  impact_confidence REAL,
  impact_update TEXT,
  accumulated_insight TEXT,

  status TEXT DEFAULT 'seed',
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS mythought_incidences (
  id TEXT PRIMARY KEY,
  hyperedge_id TEXT,
  node_type TEXT,
  node_value TEXT,
  role TEXT,
  weight REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS pathway_candidates (
  id TEXT PRIMARY KEY,
  graph_mythought_id TEXT,
  pathway_type TEXT,
  score REAL DEFAULT 0.0,
  candidate_json TEXT,
  selected INTEGER DEFAULT 0,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS selected_pathways (
  id TEXT PRIMARY KEY,
  pathway_candidate_id TEXT,
  graph_mythought_id TEXT,
  thread_id TEXT,
  selected_json TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS graph_mythoughts (
  id TEXT PRIMARY KEY,
  thread_id TEXT,
  user_text TEXT,
  graph_mythought_json TEXT,
  pathway_id TEXT,
  response_form TEXT,
  rendered_response TEXT,
  score INTEGER DEFAULT 0,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS response_forms (
  id TEXT PRIMARY KEY,
  name TEXT,
  template TEXT,
  description TEXT
);

CREATE TABLE IF NOT EXISTS rendered_responses (
  id TEXT PRIMARY KEY,
  graph_mythought_id TEXT,
  response_form TEXT,
  rendered_text TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS feedback_events (
  id TEXT PRIMARY KEY,
  graph_mythought_id TEXT,
  score INTEGER,
  tags_json TEXT,
  correction_text TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS preference_pairs (
  id TEXT PRIMARY KEY,
  thread_id TEXT,
  chosen_graph_mythought_id TEXT,
  rejected_graph_mythought_id TEXT,
  score REAL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS policy_weights (
  id TEXT PRIMARY KEY,
  from_type TEXT,
  from_value TEXT,
  to_type TEXT,
  to_value TEXT,
  weight REAL DEFAULT 0.0,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_edge
ON policy_weights(from_type, from_value, to_type, to_value);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  lineage TEXT,
  arc_length INTEGER,
  final_state TEXT,
  arc_summary TEXT
);

CREATE TABLE IF NOT EXISTS turns (
  id TEXT PRIMARY KEY,
  episode_id TEXT,
  turn_index INTEGER,
  lineage TEXT,
  user_text TEXT,
  assistant_visible_text TEXT,
  pedagogy_json TEXT
);

CREATE TABLE IF NOT EXISTS transitions (
  id TEXT PRIMARY KEY,
  episode_id TEXT,
  from_turn INTEGER,
  to_turn INTEGER,
  from_state TEXT,
  to_state TEXT,
  move_function TEXT,
  mechanism_shape TEXT,
  teaching_actions_json TEXT,
  register_json TEXT,
  predicted_impact TEXT,
  impact_update TEXT,
  prediction_match TEXT
);
