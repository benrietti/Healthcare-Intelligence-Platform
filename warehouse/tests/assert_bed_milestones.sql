select * from {{ ref('rpt_bed_readiness') }}
where ed_departure_ts < ed_arrival_ts
 or (bed_ready_ts is not null and bed_ready_ts < administrative_discharge_ts)
