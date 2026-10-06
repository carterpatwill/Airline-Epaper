-- heartbeat table for the plane-device monitor.
-- Already applied to Neon project raspy-breeze-46225705, branch br-little-pine-b8ziwwqm.
-- Kept here for reference / re-creation. Note: Neon run_sql takes ONE statement
-- per call, so apply these two separately if re-running via MCP.

CREATE TABLE heartbeat (
  id          BIGSERIAL PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id   TEXT NOT NULL,
  fw          TEXT,       -- firmware version string
  boot_count  INT,        -- RTC-persisted wake counter (spots resets)
  uptime_ms   BIGINT,     -- millis() at send time
  batt_pct    INT,        -- 0..100
  wifi_rssi   INT,        -- dBm (negative)
  http_code   INT,        -- last OpenSky HTTP status (200 = success)
  num_states  INT,        -- OpenSky states parsed this wake
  credits     INT,        -- OpenSky X-Rate-Limit-Remaining (-1 = unknown)
  free_heap   INT,        -- ESP.getFreeHeap()
  plane_valid BOOLEAN,    -- did we find a plane this wake
  callsign    TEXT,
  dist_km     REAL,
  alt_ft      INT,
  airline     TEXT,
  model       TEXT
);

CREATE INDEX heartbeat_device_recv_idx ON heartbeat (device_id, received_at DESC);
