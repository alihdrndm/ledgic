
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]

export type Database = {
  
  "graphql_public": {
          Tables: {
            [_ in never]: never
          }
          Views: {
            [_ in never]: never
          }
          Functions: {
            "graphql":
{ Args: { "extensions"?: Json,"operationName"?: string,"query"?: string,"variables"?: Json }; Returns: Json
                           }
          }
          Enums: {
            [_ in never]: never
          }
          CompositeTypes: {
            [_ in never]: never
          }
        },"public": {
          Tables: {
            "approvals": {
                  Row: {
                    "action": Database["public"]['Enums']["decision_action"],"actor_id": string,"comment": string | null,"decided_at": string,"exception_id": string,"hold_amount": number | null,"id": string,"org_id": string,"pay_amount": number | null,"time_spent_seconds": number | null
                  }
                  ComputedFields: never
                  Insert: {
                    "action": Database["public"]['Enums']["decision_action"],"actor_id": string,"comment"?: string | null,"decided_at"?: string,"exception_id": string,"hold_amount"?: number | null,"id"?: string,"org_id": string,"pay_amount"?: number | null,"time_spent_seconds"?: number | null
                  }
                  Update: {
                    "action"?: Database["public"]['Enums']["decision_action"],"actor_id"?: string,"comment"?: string | null,"decided_at"?: string,"exception_id"?: string,"hold_amount"?: number | null,"id"?: string,"org_id"?: string,"pay_amount"?: number | null,"time_spent_seconds"?: number | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "approvals_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "exceptions"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "approvals_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "exceptions_public"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "approvals_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_exception_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "approvals_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "approvals_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["open_exception_id"]
    },{
      foreignKeyName: "approvals_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_review_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "approvals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"audit_log": {
                  Row: {
                    "action": string,"actor_id": string | null,"actor_type": Database["public"]['Enums']["actor_type"],"after": Json | null,"at": string,"before": Json | null,"entity_id": string,"entity_type": string,"hash": string,"id": number,"org_id": string,"prev_hash": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "action": string,"actor_id"?: string | null,"actor_type": Database["public"]['Enums']["actor_type"],"after"?: Json | null,"at"?: string,"before"?: Json | null,"entity_id": string,"entity_type": string,"hash": string,"id"?: number,"org_id": string,"prev_hash"?: string | null
                  }
                  Update: {
                    "action"?: string,"actor_id"?: string | null,"actor_type"?: Database["public"]['Enums']["actor_type"],"after"?: Json | null,"at"?: string,"before"?: Json | null,"entity_id"?: string,"entity_type"?: string,"hash"?: string,"id"?: number,"org_id"?: string,"prev_hash"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"contract_prices": {
                  Row: {
                    "clause_ref": string,"contract_id": string,"id": string,"item_id": string,"unit_price": number,"uom": string
                  }
                  ComputedFields: never
                  Insert: {
                    "clause_ref": string,"contract_id": string,"id"?: string,"item_id": string,"unit_price": number,"uom": string
                  }
                  Update: {
                    "clause_ref"?: string,"contract_id"?: string,"id"?: string,"item_id"?: string,"unit_price"?: number,"uom"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "contract_prices_contract_id_fkey"
      columns: ["contract_id"]
isOneToOne: false
      referencedRelation: "contracts"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "contract_prices_contract_id_fkey"
      columns: ["contract_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["contract_id"]
    },{
      foreignKeyName: "contract_prices_item_id_fkey"
      columns: ["item_id"]
isOneToOne: false
      referencedRelation: "items"
      referencedColumns: ["id"]
    }
                  ]
                },"contracts": {
                  Row: {
                    "countersigned_at": string | null,"document_path": string | null,"effective_from": string,"effective_to": string,"id": string,"org_id": string,"title": string,"vendor_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "countersigned_at"?: string | null,"document_path"?: string | null,"effective_from": string,"effective_to": string,"id"?: string,"org_id": string,"title": string,"vendor_id": string
                  }
                  Update: {
                    "countersigned_at"?: string | null,"document_path"?: string | null,"effective_from"?: string,"effective_to"?: string,"id"?: string,"org_id"?: string,"title"?: string,"vendor_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "contracts_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"copilot_cache": {
                  Row: {
                    "answer": NonNullable<Json>,"created_at": string,"org_id": string,"q_hash": string,"question": string
                  }
                  ComputedFields: never
                  Insert: {
                    "answer": NonNullable<Json>,"created_at"?: string,"org_id": string,"q_hash": string,"question": string
                  }
                  Update: {
                    "answer"?: NonNullable<Json>,"created_at"?: string,"org_id"?: string,"q_hash"?: string,"question"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "copilot_cache_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"cost_ledger": {
                  Row: {
                    "amount_usd": number,"at": string,"id": number,"kind": Database["public"]['Enums']["cost_kind"],"meta": NonNullable<Json>,"org_id": string,"run_id": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "amount_usd": number,"at"?: string,"id"?: number,"kind": Database["public"]['Enums']["cost_kind"],"meta"?: NonNullable<Json>,"org_id": string,"run_id"?: string | null
                  }
                  Update: {
                    "amount_usd"?: number,"at"?: string,"id"?: number,"kind"?: Database["public"]['Enums']["cost_kind"],"meta"?: NonNullable<Json>,"org_id"?: string,"run_id"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "cost_ledger_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "cost_ledger_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "cost_ledger_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"dead_letters": {
                  Row: {
                    "created_at": string,"error": string,"id": string,"org_id": string | null,"payload": Json | null,"resolved_at": string | null,"run_id": string | null,"stage": Database["public"]['Enums']["stage"] | null
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"error": string,"id"?: string,"org_id"?: string | null,"payload"?: Json | null,"resolved_at"?: string | null,"run_id"?: string | null,"stage"?: Database["public"]['Enums']["stage"] | null
                  }
                  Update: {
                    "created_at"?: string,"error"?: string,"id"?: string,"org_id"?: string | null,"payload"?: Json | null,"resolved_at"?: string | null,"run_id"?: string | null,"stage"?: Database["public"]['Enums']["stage"] | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "dead_letters_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "dead_letters_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "dead_letters_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"documents": {
                  Row: {
                    "channel": Database["public"]['Enums']["channel"],"id": string,"mime": string,"org_id": string,"original_filename": string | null,"page_count": number | null,"phash": string | null,"preprocessing": Json | null,"received_at": string,"sha256": string,"source_meta": NonNullable<Json>,"storage_path": string
                  }
                  ComputedFields: never
                  Insert: {
                    "channel": Database["public"]['Enums']["channel"],"id"?: string,"mime": string,"org_id": string,"original_filename"?: string | null,"page_count"?: number | null,"phash"?: string | null,"preprocessing"?: Json | null,"received_at"?: string,"sha256": string,"source_meta"?: NonNullable<Json>,"storage_path": string
                  }
                  Update: {
                    "channel"?: Database["public"]['Enums']["channel"],"id"?: string,"mime"?: string,"org_id"?: string,"original_filename"?: string | null,"page_count"?: number | null,"phash"?: string | null,"preprocessing"?: Json | null,"received_at"?: string,"sha256"?: string,"source_meta"?: NonNullable<Json>,"storage_path"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"duplicate_candidates": {
                  Row: {
                    "candidate_invoice_id": string,"created_at": string,"evidence": NonNullable<Json>,"id": string,"invoice_id": string,"org_id": string,"similarity": number
                  }
                  ComputedFields: never
                  Insert: {
                    "candidate_invoice_id": string,"created_at"?: string,"evidence": NonNullable<Json>,"id"?: string,"invoice_id": string,"org_id": string,"similarity": number
                  }
                  Update: {
                    "candidate_invoice_id"?: string,"created_at"?: string,"evidence"?: NonNullable<Json>,"id"?: string,"invoice_id"?: string,"org_id"?: string,"similarity"?: number
                  }
                  Relationships: [
                    {
      foreignKeyName: "duplicate_candidates_candidate_invoice_id_fkey"
      columns: ["candidate_invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "duplicate_candidates_candidate_invoice_id_fkey"
      columns: ["candidate_invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "duplicate_candidates_candidate_invoice_id_fkey"
      columns: ["candidate_invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "duplicate_candidates_candidate_invoice_id_fkey"
      columns: ["candidate_invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "duplicate_candidates_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "duplicate_candidates_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "duplicate_candidates_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "duplicate_candidates_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "duplicate_candidates_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"entities": {
                  Row: {
                    "erp": Database["public"]['Enums']["erp_system"],"erp_company_ref": string | null,"id": string,"name": string,"org_id": string,"short_code": string
                  }
                  ComputedFields: never
                  Insert: {
                    "erp": Database["public"]['Enums']["erp_system"],"erp_company_ref"?: string | null,"id"?: string,"name": string,"org_id": string,"short_code": string
                  }
                  Update: {
                    "erp"?: Database["public"]['Enums']["erp_system"],"erp_company_ref"?: string | null,"id"?: string,"name"?: string,"org_id"?: string,"short_code"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "entities_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"erp_postings": {
                  Row: {
                    "attempts": number,"error": string | null,"external_id": string | null,"id": string,"invoice_id": string,"org_id": string,"posted_at": string | null,"request": NonNullable<Json>,"response": Json | null,"status": string,"system": Database["public"]['Enums']["erp_system"]
                  }
                  ComputedFields: never
                  Insert: {
                    "attempts"?: number,"error"?: string | null,"external_id"?: string | null,"id"?: string,"invoice_id": string,"org_id": string,"posted_at"?: string | null,"request": NonNullable<Json>,"response"?: Json | null,"status": string,"system": Database["public"]['Enums']["erp_system"]
                  }
                  Update: {
                    "attempts"?: number,"error"?: string | null,"external_id"?: string | null,"id"?: string,"invoice_id"?: string,"org_id"?: string,"posted_at"?: string | null,"request"?: NonNullable<Json>,"response"?: Json | null,"status"?: string,"system"?: Database["public"]['Enums']["erp_system"]
                  }
                  Relationships: [
                    {
      foreignKeyName: "erp_postings_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "erp_postings_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "erp_postings_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "erp_postings_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "erp_postings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"eval_runs": {
                  Row: {
                    "accuracy": number | null,"by_field": NonNullable<Json>,"created_at": string,"fields_correct": number,"fields_labeled": number,"id": string,"org_id": string | null,"prompt_version": string | null,"sample_size": number,"week_start": string
                  }
                  ComputedFields: never
                  Insert: {
                    "accuracy"?: never,"by_field": NonNullable<Json>,"created_at"?: string,"fields_correct": number,"fields_labeled": number,"id"?: string,"org_id"?: string | null,"prompt_version"?: string | null,"sample_size": number,"week_start": string
                  }
                  Update: {
                    "accuracy"?: never,"by_field"?: NonNullable<Json>,"created_at"?: string,"fields_correct"?: number,"fields_labeled"?: number,"id"?: string,"org_id"?: string | null,"prompt_version"?: string | null,"sample_size"?: number,"week_start"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_prompt_version_fkey"
      columns: ["prompt_version"]
isOneToOne: false
      referencedRelation: "prompt_versions"
      referencedColumns: ["id"]
    }
                  ]
                },"exception_drafts": {
                  Row: {
                    "body_md": string,"citations": NonNullable<Json>,"cost_usd": number,"created_at": string,"exception_id": string,"id": string,"kind": string,"mode": string,"model": string | null,"org_id": string,"prompt_version": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "body_md": string,"citations"?: NonNullable<Json>,"cost_usd"?: number,"created_at"?: string,"exception_id": string,"id"?: string,"kind": string,"mode": string,"model"?: string | null,"org_id": string,"prompt_version"?: string | null
                  }
                  Update: {
                    "body_md"?: string,"citations"?: NonNullable<Json>,"cost_usd"?: number,"created_at"?: string,"exception_id"?: string,"id"?: string,"kind"?: string,"mode"?: string,"model"?: string | null,"org_id"?: string,"prompt_version"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "exception_drafts_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "exceptions"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exception_drafts_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "exceptions_public"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exception_drafts_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_exception_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "exception_drafts_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "exception_drafts_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["open_exception_id"]
    },{
      foreignKeyName: "exception_drafts_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_review_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exception_drafts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"exceptions": {
                  Row: {
                    "amount_at_risk": number,"assigned_role": Database["public"]['Enums']["member_role"],"assigned_to": string | null,"escalated": boolean,"first_viewed_at": string | null,"id": string,"invoice_id": string,"opened_at": string,"org_id": string,"reason": string,"resolved_at": string | null,"run_id": string | null,"sla_due_at": string,"status": Database["public"]['Enums']["exception_status"],"type": Database["public"]['Enums']["exception_type"]
                  }
                  ComputedFields: never
                  Insert: {
                    "amount_at_risk"?: number,"assigned_role"?: Database["public"]['Enums']["member_role"],"assigned_to"?: string | null,"escalated"?: boolean,"first_viewed_at"?: string | null,"id"?: string,"invoice_id": string,"opened_at"?: string,"org_id": string,"reason": string,"resolved_at"?: string | null,"run_id"?: string | null,"sla_due_at": string,"status"?: Database["public"]['Enums']["exception_status"],"type": Database["public"]['Enums']["exception_type"]
                  }
                  Update: {
                    "amount_at_risk"?: number,"assigned_role"?: Database["public"]['Enums']["member_role"],"assigned_to"?: string | null,"escalated"?: boolean,"first_viewed_at"?: string | null,"id"?: string,"invoice_id"?: string,"opened_at"?: string,"org_id"?: string,"reason"?: string,"resolved_at"?: string | null,"run_id"?: string | null,"sla_due_at"?: string,"status"?: Database["public"]['Enums']["exception_status"],"type"?: Database["public"]['Enums']["exception_type"]
                  }
                  Relationships: [
                    {
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"fraud_signals": {
                  Row: {
                    "created_at": string,"detail": NonNullable<Json>,"id": string,"invoice_id": string,"org_id": string,"signal": string,"vendor_id": string | null,"weight": number
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"detail"?: NonNullable<Json>,"id"?: string,"invoice_id": string,"org_id": string,"signal": string,"vendor_id"?: string | null,"weight": number
                  }
                  Update: {
                    "created_at"?: string,"detail"?: NonNullable<Json>,"id"?: string,"invoice_id"?: string,"org_id"?: string,"signal"?: string,"vendor_id"?: string | null,"weight"?: number
                  }
                  Relationships: [
                    {
      foreignKeyName: "fraud_signals_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "fraud_signals_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "fraud_signals_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "fraud_signals_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "fraud_signals_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"gl_accounts": {
                  Row: {
                    "entity_id": string | null,"erp_ref": string | null,"id": string,"name": string,"number": string,"org_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "entity_id"?: string | null,"erp_ref"?: string | null,"id"?: string,"name": string,"number": string,"org_id": string
                  }
                  Update: {
                    "entity_id"?: string | null,"erp_ref"?: string | null,"id"?: string,"name"?: string,"number"?: string,"org_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "gl_accounts_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "entities"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "gl_accounts_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["entity_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "gl_accounts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"goods_receipts": {
                  Row: {
                    "grn_number": string,"id": string,"org_id": string,"po_id": string,"received_at": string,"received_by": string | null,"source": string
                  }
                  ComputedFields: never
                  Insert: {
                    "grn_number": string,"id"?: string,"org_id": string,"po_id": string,"received_at": string,"received_by"?: string | null,"source"?: string
                  }
                  Update: {
                    "grn_number"?: string,"id"?: string,"org_id"?: string,"po_id"?: string,"received_at"?: string,"received_by"?: string | null,"source"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "goods_receipts_po_id_fkey"
      columns: ["po_id"]
isOneToOne: false
      referencedRelation: "purchase_orders"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "goods_receipts_po_id_fkey"
      columns: ["po_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["po_id"]
    }
                  ]
                },"grn_lines": {
                  Row: {
                    "grn_id": string,"id": string,"po_line_id": string,"qty_received": number,"uom": string
                  }
                  ComputedFields: never
                  Insert: {
                    "grn_id": string,"id"?: string,"po_line_id": string,"qty_received": number,"uom": string
                  }
                  Update: {
                    "grn_id"?: string,"id"?: string,"po_line_id"?: string,"qty_received"?: number,"uom"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "grn_lines_grn_id_fkey"
      columns: ["grn_id"]
isOneToOne: false
      referencedRelation: "goods_receipts"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "grn_lines_po_line_id_fkey"
      columns: ["po_line_id"]
isOneToOne: false
      referencedRelation: "po_lines"
      referencedColumns: ["id"]
    }
                  ]
                },"integrations": {
                  Row: {
                    "config": NonNullable<Json>,"entity_id": string | null,"id": string,"last_error": string | null,"last_sync_at": string | null,"org_id": string,"provider": string,"status": string,"vault_secret_id": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "config"?: NonNullable<Json>,"entity_id"?: string | null,"id"?: string,"last_error"?: string | null,"last_sync_at"?: string | null,"org_id": string,"provider": string,"status"?: string,"vault_secret_id"?: string | null
                  }
                  Update: {
                    "config"?: NonNullable<Json>,"entity_id"?: string | null,"id"?: string,"last_error"?: string | null,"last_sync_at"?: string | null,"org_id"?: string,"provider"?: string,"status"?: string,"vault_secret_id"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "integrations_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "entities"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "integrations_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["entity_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "integrations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"invoice_fields": {
                  Row: {
                    "bbox": Json | null,"confidence": number,"field": string,"id": string,"invoice_id": string,"raw_confidence": number | null,"set_at": string,"set_by": string | null,"source": Database["public"]['Enums']["field_source"],"value": string | null,"version": number
                  }
                  ComputedFields: never
                  Insert: {
                    "bbox"?: Json | null,"confidence": number,"field": string,"id"?: string,"invoice_id": string,"raw_confidence"?: number | null,"set_at"?: string,"set_by"?: string | null,"source": Database["public"]['Enums']["field_source"],"value"?: string | null,"version"?: number
                  }
                  Update: {
                    "bbox"?: Json | null,"confidence"?: number,"field"?: string,"id"?: string,"invoice_id"?: string,"raw_confidence"?: number | null,"set_at"?: string,"set_by"?: string | null,"source"?: Database["public"]['Enums']["field_source"],"value"?: string | null,"version"?: number
                  }
                  Relationships: [
                    {
      foreignKeyName: "invoice_fields_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoice_fields_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoice_fields_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoice_fields_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    }
                  ]
                },"invoice_lines": {
                  Row: {
                    "amount": number | null,"bboxes": Json | null,"confidences": NonNullable<Json>,"description": string,"gl_account_id": string | null,"gl_confidence": number | null,"id": string,"invoice_id": string,"item_id": string | null,"line_no": number,"po_line_id": string | null,"qty": number | null,"unit_price": number | null,"uom": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "amount"?: number | null,"bboxes"?: Json | null,"confidences": NonNullable<Json>,"description": string,"gl_account_id"?: string | null,"gl_confidence"?: number | null,"id"?: string,"invoice_id": string,"item_id"?: string | null,"line_no": number,"po_line_id"?: string | null,"qty"?: number | null,"unit_price"?: number | null,"uom"?: string | null
                  }
                  Update: {
                    "amount"?: number | null,"bboxes"?: Json | null,"confidences"?: NonNullable<Json>,"description"?: string,"gl_account_id"?: string | null,"gl_confidence"?: number | null,"id"?: string,"invoice_id"?: string,"item_id"?: string | null,"line_no"?: number,"po_line_id"?: string | null,"qty"?: number | null,"unit_price"?: number | null,"uom"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "invoice_lines_gl_account_id_fkey"
      columns: ["gl_account_id"]
isOneToOne: false
      referencedRelation: "gl_accounts"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoice_lines_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoice_lines_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoice_lines_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoice_lines_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoice_lines_item_id_fkey"
      columns: ["item_id"]
isOneToOne: false
      referencedRelation: "items"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoice_lines_po_line_id_fkey"
      columns: ["po_line_id"]
isOneToOne: false
      referencedRelation: "po_lines"
      referencedColumns: ["id"]
    }
                  ]
                },"invoices": {
                  Row: {
                    "created_at": string,"currency": string,"doc_confidence": number | null,"document_id": string,"due_date": string | null,"duplicate_of": string | null,"entity_id": string | null,"extraction_mode": string | null,"freight": number | null,"gate_passed": boolean | null,"human_touches": number,"id": string,"invoice_date": string | null,"invoice_number": string | null,"invoice_number_norm": string | null,"location_id": string | null,"org_id": string,"po_id": string | null,"posted_at": string | null,"received_at": string,"status": Database["public"]['Enums']["invoice_status"],"subtotal": number | null,"tax": number | null,"terms": string | null,"total": number | null,"touchless": boolean | null,"vendor_id": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"currency"?: string,"doc_confidence"?: number | null,"document_id": string,"due_date"?: string | null,"duplicate_of"?: string | null,"entity_id"?: string | null,"extraction_mode"?: string | null,"freight"?: number | null,"gate_passed"?: boolean | null,"human_touches"?: number,"id"?: string,"invoice_date"?: string | null,"invoice_number"?: string | null,"invoice_number_norm"?: never,"location_id"?: string | null,"org_id": string,"po_id"?: string | null,"posted_at"?: string | null,"received_at": string,"status"?: Database["public"]['Enums']["invoice_status"],"subtotal"?: number | null,"tax"?: number | null,"terms"?: string | null,"total"?: number | null,"touchless"?: boolean | null,"vendor_id"?: string | null
                  }
                  Update: {
                    "created_at"?: string,"currency"?: string,"doc_confidence"?: number | null,"document_id"?: string,"due_date"?: string | null,"duplicate_of"?: string | null,"entity_id"?: string | null,"extraction_mode"?: string | null,"freight"?: number | null,"gate_passed"?: boolean | null,"human_touches"?: number,"id"?: string,"invoice_date"?: string | null,"invoice_number"?: string | null,"invoice_number_norm"?: never,"location_id"?: string | null,"org_id"?: string,"po_id"?: string | null,"posted_at"?: string | null,"received_at"?: string,"status"?: Database["public"]['Enums']["invoice_status"],"subtotal"?: number | null,"tax"?: number | null,"terms"?: string | null,"total"?: number | null,"touchless"?: boolean | null,"vendor_id"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "invoices_document_id_fkey"
      columns: ["document_id"]
isOneToOne: false
      referencedRelation: "documents"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoices_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "entities"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["entity_id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "locations"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_po_id_fkey"
      columns: ["po_id"]
isOneToOne: false
      referencedRelation: "purchase_orders"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_po_id_fkey"
      columns: ["po_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["po_id"]
    },{
      foreignKeyName: "invoices_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"items": {
                  Row: {
                    "default_gl": string | null,"description": string,"embedding": string | null,"id": string,"item_key": string,"org_id": string,"uom": string
                  }
                  ComputedFields: never
                  Insert: {
                    "default_gl"?: string | null,"description": string,"embedding"?: string | null,"id"?: string,"item_key": string,"org_id": string,"uom": string
                  }
                  Update: {
                    "default_gl"?: string | null,"description"?: string,"embedding"?: string | null,"id"?: string,"item_key"?: string,"org_id"?: string,"uom"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "items_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"kb_chunks": {
                  Row: {
                    "clause_ref": string | null,"content": string,"document_id": string,"embedding": string | null,"heading_path": string | null,"id": string,"ord": number,"org_id": string,"tsv": unknown
                  }
                  ComputedFields: never
                  Insert: {
                    "clause_ref"?: string | null,"content": string,"document_id": string,"embedding"?: string | null,"heading_path"?: string | null,"id"?: string,"ord": number,"org_id": string,"tsv"?: never
                  }
                  Update: {
                    "clause_ref"?: string | null,"content"?: string,"document_id"?: string,"embedding"?: string | null,"heading_path"?: string | null,"id"?: string,"ord"?: number,"org_id"?: string,"tsv"?: never
                  }
                  Relationships: [
                    {
      foreignKeyName: "kb_chunks_document_id_fkey"
      columns: ["document_id"]
isOneToOne: false
      referencedRelation: "kb_documents"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_chunks_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"kb_documents": {
                  Row: {
                    "contract_id": string | null,"created_at": string,"id": string,"kind": string,"org_id": string,"source_path": string | null,"title": string,"vendor_id": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "contract_id"?: string | null,"created_at"?: string,"id"?: string,"kind": string,"org_id": string,"source_path"?: string | null,"title": string,"vendor_id"?: string | null
                  }
                  Update: {
                    "contract_id"?: string | null,"created_at"?: string,"id"?: string,"kind"?: string,"org_id"?: string,"source_path"?: string | null,"title"?: string,"vendor_id"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "kb_documents_contract_id_fkey"
      columns: ["contract_id"]
isOneToOne: false
      referencedRelation: "contracts"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "kb_documents_contract_id_fkey"
      columns: ["contract_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["contract_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "kb_documents_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"llm_budget": {
                  Row: {
                    "cap_usd": number,"day": string,"reserved_usd": number,"spent_usd": number
                  }
                  ComputedFields: never
                  Insert: {
                    "cap_usd": number,"day": string,"reserved_usd"?: number,"spent_usd"?: number
                  }
                  Update: {
                    "cap_usd"?: number,"day"?: string,"reserved_usd"?: number,"spent_usd"?: number
                  }
                  Relationships: [
                    
                  ]
                },"llm_budget_reservations": {
                  Row: {
                    "actual_usd": number | null,"created_at": string,"day": string,"est_usd": number,"id": string,"settled_at": string | null,"status": string
                  }
                  ComputedFields: never
                  Insert: {
                    "actual_usd"?: number | null,"created_at"?: string,"day": string,"est_usd": number,"id"?: string,"settled_at"?: string | null,"status"?: string
                  }
                  Update: {
                    "actual_usd"?: number | null,"created_at"?: string,"day"?: string,"est_usd"?: number,"id"?: string,"settled_at"?: string | null,"status"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "llm_budget_reservations_day_fkey"
      columns: ["day"]
isOneToOne: false
      referencedRelation: "llm_budget"
      referencedColumns: ["day"]
    }
                  ]
                },"locations": {
                  Row: {
                    "code": string,"entity_id": string,"erp_class_ref": string | null,"id": string,"name": string,"org_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "code": string,"entity_id": string,"erp_class_ref"?: string | null,"id"?: string,"name": string,"org_id": string
                  }
                  Update: {
                    "code"?: string,"entity_id"?: string,"erp_class_ref"?: string | null,"id"?: string,"name"?: string,"org_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "locations_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "entities"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "locations_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["entity_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "locations_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"match_line_results": {
                  Row: {
                    "allowed_amount": number | null,"contract_price_id": string | null,"delta_amount": number | null,"delta_pct": number | null,"expected_amount": number | null,"expected_source": string | null,"expected_unit_price": number | null,"grn_qty": number | null,"id": string,"invoice_line_id": string,"match_result_id": string,"note": string | null,"po_line_id": string | null,"verdict": Database["public"]['Enums']["line_verdict"]
                  }
                  ComputedFields: never
                  Insert: {
                    "allowed_amount"?: number | null,"contract_price_id"?: string | null,"delta_amount"?: number | null,"delta_pct"?: number | null,"expected_amount"?: number | null,"expected_source"?: string | null,"expected_unit_price"?: number | null,"grn_qty"?: number | null,"id"?: string,"invoice_line_id": string,"match_result_id": string,"note"?: string | null,"po_line_id"?: string | null,"verdict": Database["public"]['Enums']["line_verdict"]
                  }
                  Update: {
                    "allowed_amount"?: number | null,"contract_price_id"?: string | null,"delta_amount"?: number | null,"delta_pct"?: number | null,"expected_amount"?: number | null,"expected_source"?: string | null,"expected_unit_price"?: number | null,"grn_qty"?: number | null,"id"?: string,"invoice_line_id"?: string,"match_result_id"?: string,"note"?: string | null,"po_line_id"?: string | null,"verdict"?: Database["public"]['Enums']["line_verdict"]
                  }
                  Relationships: [
                    {
      foreignKeyName: "match_line_results_contract_price_id_fkey"
      columns: ["contract_price_id"]
isOneToOne: false
      referencedRelation: "contract_prices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "match_line_results_invoice_line_id_fkey"
      columns: ["invoice_line_id"]
isOneToOne: false
      referencedRelation: "invoice_lines"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "match_line_results_invoice_line_id_fkey"
      columns: ["invoice_line_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_line_id"]
    },{
      foreignKeyName: "match_line_results_match_result_id_fkey"
      columns: ["match_result_id"]
isOneToOne: false
      referencedRelation: "match_results"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "match_line_results_match_result_id_fkey"
      columns: ["match_result_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["match_result_id"]
    },{
      foreignKeyName: "match_line_results_po_line_id_fkey"
      columns: ["po_line_id"]
isOneToOne: false
      referencedRelation: "po_lines"
      referencedColumns: ["id"]
    }
                  ]
                },"match_results": {
                  Row: {
                    "computed_at": string,"duration_ms": number,"expected_total": number,"id": string,"invoice_id": string,"lines_total": number,"lines_verified": number,"tolerance_abs": number,"tolerance_pct": number,"total_delta": number,"verdict": Database["public"]['Enums']["invoice_verdict"]
                  }
                  ComputedFields: never
                  Insert: {
                    "computed_at"?: string,"duration_ms": number,"expected_total": number,"id"?: string,"invoice_id": string,"lines_total": number,"lines_verified": number,"tolerance_abs": number,"tolerance_pct": number,"total_delta": number,"verdict": Database["public"]['Enums']["invoice_verdict"]
                  }
                  Update: {
                    "computed_at"?: string,"duration_ms"?: number,"expected_total"?: number,"id"?: string,"invoice_id"?: string,"lines_total"?: number,"lines_verified"?: number,"tolerance_abs"?: number,"tolerance_pct"?: number,"total_delta"?: number,"verdict"?: Database["public"]['Enums']["invoice_verdict"]
                  }
                  Relationships: [
                    {
      foreignKeyName: "match_results_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: true
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "match_results_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: true
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "match_results_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: true
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "match_results_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: true
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    }
                  ]
                },"mcp_tokens": {
                  Row: {
                    "created_at": string,"id": string,"last_used_at": string | null,"name": string,"org_id": string,"revoked_at": string | null,"scopes": (string)[],"token_hash": string,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"id"?: string,"last_used_at"?: string | null,"name": string,"org_id": string,"revoked_at"?: string | null,"scopes"?: (string)[],"token_hash": string,"user_id": string
                  }
                  Update: {
                    "created_at"?: string,"id"?: string,"last_used_at"?: string | null,"name"?: string,"org_id"?: string,"revoked_at"?: string | null,"scopes"?: (string)[],"token_hash"?: string,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "mcp_tokens_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"memberships": {
                  Row: {
                    "created_at": string,"org_id": string,"role": Database["public"]['Enums']["member_role"],"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"org_id": string,"role": Database["public"]['Enums']["member_role"],"user_id": string
                  }
                  Update: {
                    "created_at"?: string,"org_id"?: string,"role"?: Database["public"]['Enums']["member_role"],"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "memberships_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"org_settings": {
                  Row: {
                    "confidence_gate": number,"controller_notify_threshold": number,"dup_hold_threshold": number,"dup_suggest_threshold": number,"field_floor": number,"fraud_hold_threshold": number,"infra_monthly_usd": number,"loaded_hourly_rate_usd": number,"manager_limit": number,"org_id": string,"over_receipt_allowance": number,"sla_hours": number,"slack_digest_local_time": string,"updated_at": string
                  }
                  ComputedFields: never
                  Insert: {
                    "confidence_gate"?: number,"controller_notify_threshold"?: number,"dup_hold_threshold"?: number,"dup_suggest_threshold"?: number,"field_floor"?: number,"fraud_hold_threshold"?: number,"infra_monthly_usd"?: number,"loaded_hourly_rate_usd"?: number,"manager_limit"?: number,"org_id": string,"over_receipt_allowance"?: number,"sla_hours"?: number,"slack_digest_local_time"?: string,"updated_at"?: string
                  }
                  Update: {
                    "confidence_gate"?: number,"controller_notify_threshold"?: number,"dup_hold_threshold"?: number,"dup_suggest_threshold"?: number,"field_floor"?: number,"fraud_hold_threshold"?: number,"infra_monthly_usd"?: number,"loaded_hourly_rate_usd"?: number,"manager_limit"?: number,"org_id"?: string,"over_receipt_allowance"?: number,"sla_hours"?: number,"slack_digest_local_time"?: string,"updated_at"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "org_settings_org_id_fkey"
      columns: ["org_id"]
isOneToOne: true
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"orgs": {
                  Row: {
                    "created_at": string,"id": string,"is_demo": boolean,"name": string,"slug": string,"timezone": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"id"?: string,"is_demo"?: boolean,"name": string,"slug": string,"timezone"?: string
                  }
                  Update: {
                    "created_at"?: string,"id"?: string,"is_demo"?: boolean,"name"?: string,"slug"?: string,"timezone"?: string
                  }
                  Relationships: [
                    
                  ]
                },"pipeline_events": {
                  Row: {
                    "at": string,"detail": NonNullable<Json>,"duration_ms": number | null,"id": number,"org_id": string,"run_id": string,"stage": Database["public"]['Enums']["stage"],"status": Database["public"]['Enums']["event_status"],"summary": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "at"?: string,"detail"?: NonNullable<Json>,"duration_ms"?: number | null,"id"?: number,"org_id": string,"run_id": string,"stage": Database["public"]['Enums']["stage"],"status": Database["public"]['Enums']["event_status"],"summary"?: string | null
                  }
                  Update: {
                    "at"?: string,"detail"?: NonNullable<Json>,"duration_ms"?: number | null,"id"?: number,"org_id"?: string,"run_id"?: string,"stage"?: Database["public"]['Enums']["stage"],"status"?: Database["public"]['Enums']["event_status"],"summary"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_events_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "pipeline_events_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"pipeline_runs": {
                  Row: {
                    "attempt": number,"context": NonNullable<Json>,"current_stage": Database["public"]['Enums']["stage"],"document_id": string,"finished_at": string | null,"id": string,"invoice_id": string | null,"last_error": string | null,"lease_owner": string | null,"lease_until": string | null,"next_attempt_at": string | null,"next_stage": Database["public"]['Enums']["stage"] | null,"orchestrator_version": string | null,"org_id": string,"run_number": number,"started_at": string,"status": string,"wait_exception_id": string | null,"workflow_version": string
                  }
                  ComputedFields: never
                  Insert: {
                    "attempt"?: number,"context"?: NonNullable<Json>,"current_stage"?: Database["public"]['Enums']["stage"],"document_id": string,"finished_at"?: string | null,"id"?: string,"invoice_id"?: string | null,"last_error"?: string | null,"lease_owner"?: string | null,"lease_until"?: string | null,"next_attempt_at"?: string | null,"next_stage"?: Database["public"]['Enums']["stage"] | null,"orchestrator_version"?: string | null,"org_id": string,"run_number"?: number,"started_at"?: string,"status"?: string,"wait_exception_id"?: string | null,"workflow_version"?: string
                  }
                  Update: {
                    "attempt"?: number,"context"?: NonNullable<Json>,"current_stage"?: Database["public"]['Enums']["stage"],"document_id"?: string,"finished_at"?: string | null,"id"?: string,"invoice_id"?: string | null,"last_error"?: string | null,"lease_owner"?: string | null,"lease_until"?: string | null,"next_attempt_at"?: string | null,"next_stage"?: Database["public"]['Enums']["stage"] | null,"orchestrator_version"?: string | null,"org_id"?: string,"run_number"?: number,"started_at"?: string,"status"?: string,"wait_exception_id"?: string | null,"workflow_version"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "pipeline_runs_document_id_fkey"
      columns: ["document_id"]
isOneToOne: false
      referencedRelation: "documents"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "pipeline_runs_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "pipeline_runs_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_wait_exception_fk"
      columns: ["wait_exception_id"]
isOneToOne: false
      referencedRelation: "exceptions"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_wait_exception_fk"
      columns: ["wait_exception_id"]
isOneToOne: false
      referencedRelation: "exceptions_public"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_wait_exception_fk"
      columns: ["wait_exception_id"]
isOneToOne: false
      referencedRelation: "v_exception_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "pipeline_runs_wait_exception_fk"
      columns: ["wait_exception_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "pipeline_runs_wait_exception_fk"
      columns: ["wait_exception_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["open_exception_id"]
    },{
      foreignKeyName: "pipeline_runs_wait_exception_fk"
      columns: ["wait_exception_id"]
isOneToOne: false
      referencedRelation: "v_review_queue"
      referencedColumns: ["exception_id"]
    }
                  ]
                },"po_lines": {
                  Row: {
                    "amount": number,"description": string,"id": string,"item_id": string | null,"line_no": number,"po_id": string,"qty": number,"unit_price": number,"uom": string
                  }
                  ComputedFields: never
                  Insert: {
                    "amount": number,"description": string,"id"?: string,"item_id"?: string | null,"line_no": number,"po_id": string,"qty": number,"unit_price": number,"uom": string
                  }
                  Update: {
                    "amount"?: number,"description"?: string,"id"?: string,"item_id"?: string | null,"line_no"?: number,"po_id"?: string,"qty"?: number,"unit_price"?: number,"uom"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "po_lines_item_id_fkey"
      columns: ["item_id"]
isOneToOne: false
      referencedRelation: "items"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "po_lines_po_id_fkey"
      columns: ["po_id"]
isOneToOne: false
      referencedRelation: "purchase_orders"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "po_lines_po_id_fkey"
      columns: ["po_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["po_id"]
    }
                  ]
                },"profiles": {
                  Row: {
                    "created_at": string,"full_name": string,"initials": string,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"full_name": string,"initials": string,"user_id": string
                  }
                  Update: {
                    "created_at"?: string,"full_name"?: string,"initials"?: string,"user_id"?: string
                  }
                  Relationships: [
                    
                  ]
                },"prompt_versions": {
                  Row: {
                    "deployed_at": string,"id": string,"model": string,"notes": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "deployed_at": string,"id": string,"model": string,"notes"?: string | null
                  }
                  Update: {
                    "deployed_at"?: string,"id"?: string,"model"?: string,"notes"?: string | null
                  }
                  Relationships: [
                    
                  ]
                },"purchase_orders": {
                  Row: {
                    "entity_id": string,"erp_ref": string | null,"id": string,"location_id": string,"ordered_at": string,"org_id": string,"po_number": string,"source": string,"status": string,"total": number,"vendor_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "entity_id": string,"erp_ref"?: string | null,"id"?: string,"location_id": string,"ordered_at": string,"org_id": string,"po_number": string,"source"?: string,"status"?: string,"total": number,"vendor_id": string
                  }
                  Update: {
                    "entity_id"?: string,"erp_ref"?: string | null,"id"?: string,"location_id"?: string,"ordered_at"?: string,"org_id"?: string,"po_number"?: string,"source"?: string,"status"?: string,"total"?: number,"vendor_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "purchase_orders_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "entities"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "purchase_orders_entity_id_fkey"
      columns: ["entity_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["entity_id"]
    },{
      foreignKeyName: "purchase_orders_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "locations"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "purchase_orders_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "purchase_orders_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "purchase_orders_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "purchase_orders_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"rate_limits": {
                  Row: {
                    "count": number,"key": string,"window_start": string
                  }
                  ComputedFields: never
                  Insert: {
                    "count"?: number,"key": string,"window_start": string
                  }
                  Update: {
                    "count"?: number,"key"?: string,"window_start"?: string
                  }
                  Relationships: [
                    
                  ]
                },"recommendations": {
                  Row: {
                    "action": Database["public"]['Enums']["decision_action"],"confidence": number,"exception_id": string,"hold_amount": number | null,"id": string,"pay_amount": number | null,"reasons": NonNullable<Json>
                  }
                  ComputedFields: never
                  Insert: {
                    "action": Database["public"]['Enums']["decision_action"],"confidence": number,"exception_id": string,"hold_amount"?: number | null,"id"?: string,"pay_amount"?: number | null,"reasons": NonNullable<Json>
                  }
                  Update: {
                    "action"?: Database["public"]['Enums']["decision_action"],"confidence"?: number,"exception_id"?: string,"hold_amount"?: number | null,"id"?: string,"pay_amount"?: number | null,"reasons"?: NonNullable<Json>
                  }
                  Relationships: [
                    {
      foreignKeyName: "recommendations_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: true
      referencedRelation: "exceptions"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "recommendations_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: true
      referencedRelation: "exceptions_public"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "recommendations_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: true
      referencedRelation: "v_exception_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "recommendations_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: true
      referencedRelation: "v_match_detail"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "recommendations_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: true
      referencedRelation: "v_recent_runs"
      referencedColumns: ["open_exception_id"]
    },{
      foreignKeyName: "recommendations_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: true
      referencedRelation: "v_review_queue"
      referencedColumns: ["exception_id"]
    }
                  ]
                },"tolerance_policies": {
                  Row: {
                    "abs_amount": number,"created_at": string,"created_by": string | null,"effective_from": string,"id": string,"org_id": string,"pct": number
                  }
                  ComputedFields: never
                  Insert: {
                    "abs_amount"?: number,"created_at"?: string,"created_by"?: string | null,"effective_from"?: string,"id"?: string,"org_id": string,"pct"?: number
                  }
                  Update: {
                    "abs_amount"?: number,"created_at"?: string,"created_by"?: string | null,"effective_from"?: string,"id"?: string,"org_id"?: string,"pct"?: number
                  }
                  Relationships: [
                    {
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "tolerance_policies_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"ui_events": {
                  Row: {
                    "at": string,"exception_id": string | null,"id": number,"kind": string,"org_id": string,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "at"?: string,"exception_id"?: string | null,"id"?: number,"kind": string,"org_id": string,"user_id": string
                  }
                  Update: {
                    "at"?: string,"exception_id"?: string | null,"id"?: number,"kind"?: string,"org_id"?: string,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "ui_events_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "exceptions"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "ui_events_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "exceptions_public"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "ui_events_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_exception_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "ui_events_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "ui_events_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["open_exception_id"]
    },{
      foreignKeyName: "ui_events_exception_id_fkey"
      columns: ["exception_id"]
isOneToOne: false
      referencedRelation: "v_review_queue"
      referencedColumns: ["exception_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "ui_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"vendor_aliases": {
                  Row: {
                    "alias": string,"vendor_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "alias": string,"vendor_id": string
                  }
                  Update: {
                    "alias"?: string,"vendor_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "vendor_aliases_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"vendors": {
                  Row: {
                    "bank_fingerprint": string | null,"bank_last4": string | null,"category": string | null,"contact_email": string | null,"created_at": string,"created_by": string | null,"display_name": string,"erp_vendor_ref": Json | null,"id": string,"legal_name": string | null,"match_mode": Database["public"]['Enums']["match_mode"],"org_id": string,"remit_address": Json | null,"remit_address_changed_at": string | null,"tax_id_hash": string | null,"tax_id_last4": string | null,"w9_bank_fingerprint": string | null,"w9_on_file": boolean
                  }
                  ComputedFields: never
                  Insert: {
                    "bank_fingerprint"?: string | null,"bank_last4"?: string | null,"category"?: string | null,"contact_email"?: string | null,"created_at"?: string,"created_by"?: string | null,"display_name": string,"erp_vendor_ref"?: Json | null,"id"?: string,"legal_name"?: string | null,"match_mode"?: Database["public"]['Enums']["match_mode"],"org_id": string,"remit_address"?: Json | null,"remit_address_changed_at"?: string | null,"tax_id_hash"?: string | null,"tax_id_last4"?: string | null,"w9_bank_fingerprint"?: string | null,"w9_on_file"?: boolean
                  }
                  Update: {
                    "bank_fingerprint"?: string | null,"bank_last4"?: string | null,"category"?: string | null,"contact_email"?: string | null,"created_at"?: string,"created_by"?: string | null,"display_name"?: string,"erp_vendor_ref"?: Json | null,"id"?: string,"legal_name"?: string | null,"match_mode"?: Database["public"]['Enums']["match_mode"],"org_id"?: string,"remit_address"?: Json | null,"remit_address_changed_at"?: string | null,"tax_id_hash"?: string | null,"tax_id_last4"?: string | null,"w9_bank_fingerprint"?: string | null,"w9_on_file"?: boolean
                  }
                  Relationships: [
                    {
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "vendors_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                }
          }
          Views: {
            "exceptions_public": {
                  Row: {
                    "amount_at_risk": number | null,"assigned_role": Database["public"]['Enums']["member_role"] | null,"assigned_to": string | null,"escalated": boolean | null,"first_viewed_at": string | null,"id": string | null,"invoice_id": string | null,"opened_at": string | null,"org_id": string | null,"reason": string | null,"resolved_at": string | null,"run_id": string | null,"sla_due_at": string | null,"status": Database["public"]['Enums']["exception_status"] | null,"type": Database["public"]['Enums']["exception_type"] | null
                  }
                  ComputedFields: never
                  Insert: {
                           "amount_at_risk"?: number | null,"assigned_role"?: Database["public"]['Enums']["member_role"] | null,"assigned_to"?: string | null,"escalated"?: boolean | null,"first_viewed_at"?: string | null,"id"?: string | null,"invoice_id"?: string | null,"opened_at"?: string | null,"org_id"?: string | null,"reason"?: string | null,"resolved_at"?: string | null,"run_id"?: string | null,"sla_due_at"?: string | null,"status"?: Database["public"]['Enums']["exception_status"] | null,"type"?: Database["public"]['Enums']["exception_type"] | null
                         }
                        Update: {
                           "amount_at_risk"?: number | null,"assigned_role"?: Database["public"]['Enums']["member_role"] | null,"assigned_to"?: string | null,"escalated"?: boolean | null,"first_viewed_at"?: string | null,"id"?: string | null,"invoice_id"?: string | null,"opened_at"?: string | null,"org_id"?: string | null,"reason"?: string | null,"resolved_at"?: string | null,"run_id"?: string | null,"sla_due_at"?: string | null,"status"?: Database["public"]['Enums']["exception_status"] | null,"type"?: Database["public"]['Enums']["exception_type"] | null
                         }
                        Relationships: [
                    {
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"mv_eval_weekly": {
                  Row: {
                    "accuracy": number | null,"org_id": string | null,"prompt_deployed_at": string | null,"prompt_version": string | null,"sample_size": number | null,"week_index": number | null,"week_start": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_prompt_version_fkey"
      columns: ["prompt_version"]
isOneToOne: false
      referencedRelation: "prompt_versions"
      referencedColumns: ["id"]
    }
                  ]
                },"mv_location_period": {
                  Row: {
                    "exception_rate": number | null,"location_code": string | null,"location_id": string | null,"location_name": string | null,"locations_total": number | null,"org_id": string | null,"org_median_exception_rate": number | null,"period_key": string | null,"rank": number | null,"vendors_without_contract": number | null,"volume": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"mv_ops_period": {
                  Row: {
                    "avg_decision_seconds": number | null,"cost_human": number | null,"cost_infra": number | null,"cost_llm": number | null,"cost_ocr": number | null,"cost_per_invoice": number | null,"cost_total": number | null,"decisions_logged_pct": number | null,"entities": number | null,"erp_sync": Json | null,"held_duplicates": number | null,"held_fraud": number | null,"held_total": number | null,"held_variances": number | null,"invoices": number | null,"locations": number | null,"median_cycle_seconds": number | null,"org_id": string | null,"period_end": string | null,"period_key": string | null,"period_start": string | null,"refreshed_at": string | null,"short_pays_accepted": number | null,"top_catches": Json | null,"touchless_rate": number | null,"touchless_rate_first_week": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_ai_budget_today": {
                  Row: {
                    "cap_usd": number | null,"day": string | null,"exhausted": boolean | null,"remaining_usd": number | null,"reserved_usd": number | null,"spent_usd": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_channel_today": {
                  Row: {
                    "channel": Database["public"]['Enums']["channel"] | null,"count": number | null,"org_id": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_eval_weekly": {
                  Row: {
                    "accuracy": number | null,"org_id": string | null,"prompt_deployed_at": string | null,"prompt_version": string | null,"sample_size": number | null,"week_index": number | null,"week_start": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "eval_runs_prompt_version_fkey"
      columns: ["prompt_version"]
isOneToOne: false
      referencedRelation: "prompt_versions"
      referencedColumns: ["id"]
    }
                  ]
                },"v_exception_queue": {
                  Row: {
                    "age_seconds": number | null,"amount_at_risk": number | null,"assigned_role": Database["public"]['Enums']["member_role"] | null,"assigned_to": string | null,"assigned_to_name": string | null,"duplicate_evidence": Json | null,"escalated": boolean | null,"exception_id": string | null,"first_viewed_at": string | null,"group_label": string | null,"has_draft": boolean | null,"invoice_id": string | null,"invoice_number": string | null,"invoice_total": number | null,"is_risk_group": boolean | null,"latest_decision": Json | null,"location_name": string | null,"opened_at": string | null,"org_id": string | null,"payment_blocked": boolean | null,"reason": string | null,"recommendation": Json | null,"resolved_at": string | null,"run_id": string | null,"signal_score": number | null,"signals": Json | null,"similarity": number | null,"sla_due_at": string | null,"status": Database["public"]['Enums']["exception_status"] | null,"type": Database["public"]['Enums']["exception_type"] | null,"vendor_id": string | null,"vendor_name": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "invoices_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"v_invoice_audit": {
                  Row: {
                    "action": string | null,"actor_id": string | null,"actor_name": string | null,"actor_type": Database["public"]['Enums']["actor_type"] | null,"after": Json | null,"at": string | null,"audit_id": number | null,"before": Json | null,"entity_id": string | null,"entity_type": string | null,"hash": string | null,"invoice_key": string | null,"org_id": string | null,"prev_hash": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "audit_log_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"v_invoice_detail": {
                  Row: {
                    "channel": Database["public"]['Enums']["channel"] | null,"currency": string | null,"doc_confidence": number | null,"document_id": string | null,"due_date": string | null,"duplicate_of": string | null,"entity_id": string | null,"entity_name": string | null,"entity_short_code": string | null,"erp_external_id": string | null,"erp_status": string | null,"erp_system": Database["public"]['Enums']["erp_system"] | null,"extraction_mode": string | null,"fields": Json | null,"freight": number | null,"gate_passed": boolean | null,"grn_in_full": boolean | null,"grn_numbers": (string)[] | null,"grn_received_at": string | null,"human_touches": number | null,"invoice_date": string | null,"invoice_id": string | null,"invoice_number": string | null,"lines": Json | null,"location_code": string | null,"location_id": string | null,"location_name": string | null,"mime": string | null,"org_id": string | null,"original_filename": string | null,"page_count": number | null,"po_id": string | null,"po_number": string | null,"po_source": string | null,"po_total": number | null,"posted_at": string | null,"preprocessing": Json | null,"received_at": string | null,"run_id": string | null,"run_number": number | null,"source_meta": Json | null,"status": Database["public"]['Enums']["invoice_status"] | null,"storage_path": string | null,"subtotal": number | null,"tax": number | null,"terms": string | null,"total": number | null,"touchless": boolean | null,"vendor_category": string | null,"vendor_id": string | null,"vendor_legal_name": string | null,"vendor_name": string | null,"workflow_version": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "invoices_document_id_fkey"
      columns: ["document_id"]
isOneToOne: false
      referencedRelation: "documents"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoices_duplicate_of_fkey"
      columns: ["duplicate_of"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    }
                  ]
                },"v_kpi_periods": {
                  Row: {
                    "days": number | null,"month_days": number | null,"org_id": string | null,"period_end": string | null,"period_key": string | null,"period_start": string | null,"timezone": string | null,"ts0": string | null,"ts1": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_location_period": {
                  Row: {
                    "exception_rate": number | null,"location_code": string | null,"location_id": string | null,"location_name": string | null,"locations_total": number | null,"org_id": string | null,"org_median_exception_rate": number | null,"period_key": string | null,"rank": number | null,"vendors_without_contract": number | null,"volume": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_match_detail": {
                  Row: {
                    "allowed_amount": number | null,"clause_ref": string | null,"computed_at": string | null,"contract_document_path": string | null,"contract_effective_to": string | null,"contract_id": string | null,"contract_title": string | null,"decision": Json | null,"delta_amount": number | null,"delta_pct": number | null,"description": string | null,"duration_ms": number | null,"exception_id": string | null,"expected_amount": number | null,"expected_source": string | null,"expected_total": number | null,"expected_unit_price": number | null,"grn_qty": number | null,"inv_amount": number | null,"inv_qty": number | null,"inv_unit_price": number | null,"invoice_id": string | null,"invoice_line_id": string | null,"line_no": number | null,"line_verdict": Database["public"]['Enums']["line_verdict"] | null,"lines_total": number | null,"lines_verified": number | null,"match_result_id": string | null,"note": string | null,"org_id": string | null,"po_amount": number | null,"po_line_id": string | null,"po_qty": number | null,"po_unit_price": number | null,"recommendation": Json | null,"tolerance_abs": number | null,"tolerance_pct": number | null,"total_delta": number | null,"uom": string | null,"verdict": Database["public"]['Enums']["invoice_verdict"] | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "invoices_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"v_ops_period": {
                  Row: {
                    "avg_decision_seconds": number | null,"cost_human": number | null,"cost_infra": number | null,"cost_llm": number | null,"cost_ocr": number | null,"cost_per_invoice": number | null,"cost_total": number | null,"decisions_logged_pct": number | null,"entities": number | null,"erp_sync": Json | null,"held_duplicates": number | null,"held_fraud": number | null,"held_total": number | null,"held_variances": number | null,"invoices": number | null,"locations": number | null,"median_cycle_seconds": number | null,"org_id": string | null,"period_end": string | null,"period_key": string | null,"period_start": string | null,"refreshed_at": string | null,"short_pays_accepted": number | null,"top_catches": Json | null,"touchless_rate": number | null,"touchless_rate_first_week": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_org_today": {
                  Row: {
                    "day": string | null,"org_id": string | null,"t0": string | null,"t1": string | null,"timezone": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_pipeline_today": {
                  Row: {
                    "day": string | null,"enriched_po_linked": number | null,"extracted_above_gate": number | null,"matched_clean": number | null,"org_id": string | null,"received": number | null,"routed_to_people": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_recent_runs": {
                  Row: {
                    "channel": Database["public"]['Enums']["channel"] | null,"current_stage": Database["public"]['Enums']["stage"] | null,"end_to_end_seconds": number | null,"entity_short_code": string | null,"erp_external_id": string | null,"erp_system": Database["public"]['Enums']["erp_system"] | null,"finished_at": string | null,"invoice_id": string | null,"invoice_number": string | null,"invoice_status": Database["public"]['Enums']["invoice_status"] | null,"is_exception": boolean | null,"location_code": string | null,"location_id": string | null,"location_name": string | null,"open_exception_id": string | null,"open_exception_type": Database["public"]['Enums']["exception_type"] | null,"org_id": string | null,"run_id": string | null,"run_number": number | null,"run_status": string | null,"started_at": string | null,"status_label": string | null,"total": number | null,"touchless": boolean | null,"vendor_id": string | null,"vendor_name": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "locations"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "invoices_location_id_fkey"
      columns: ["location_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["location_id"]
    },{
      foreignKeyName: "invoices_vendor_id_fkey"
      columns: ["vendor_id"]
isOneToOne: false
      referencedRelation: "vendors"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_runs_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    }
                  ]
                },"v_review_queue": {
                  Row: {
                    "channel": Database["public"]['Enums']["channel"] | null,"doc_confidence": number | null,"exception_id": string | null,"flagged_count": number | null,"invoice_id": string | null,"invoice_number": string | null,"location_name": string | null,"opened_at": string | null,"org_id": string | null,"original_filename": string | null,"queue_position": number | null,"queue_size": number | null,"run_id": string | null,"vendor_name": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "invoices"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_match_detail"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_invoice_id_fkey"
      columns: ["invoice_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["invoice_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "exceptions_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"v_run_timeline": {
                  Row: {
                    "actor_name": string | null,"at": string | null,"detail": Json | null,"duration_ms": number | null,"event_id": number | null,"org_id": string | null,"run_id": string | null,"stage": Database["public"]['Enums']["stage"] | null,"status": Database["public"]['Enums']["event_status"] | null,"summary": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    {
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "mv_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "orgs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_channel_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_kpi_periods"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_location_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_ops_period"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_org_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_pipeline_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_stage_today"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_org_id_fkey"
      columns: ["org_id"]
isOneToOne: false
      referencedRelation: "v_status_bar"
      referencedColumns: ["org_id"]
    },{
      foreignKeyName: "pipeline_events_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "pipeline_runs"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "pipeline_events_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_invoice_detail"
      referencedColumns: ["run_id"]
    },{
      foreignKeyName: "pipeline_events_run_id_fkey"
      columns: ["run_id"]
isOneToOne: false
      referencedRelation: "v_recent_runs"
      referencedColumns: ["run_id"]
    }
                  ]
                },"v_stage_today": {
                  Row: {
                    "awaiting_person": number | null,"confidence_gate": number | null,"duplicate_screened": number | null,"extraction_auto_passed": number | null,"extraction_below_gate": number | null,"extraction_median_seconds": number | null,"field_floor": number | null,"gl_predicted": number | null,"match_clean": number | null,"match_no_po": number | null,"match_price_variance": number | null,"match_qty_mismatch": number | null,"org_id": string | null,"po_linked": number | null,"posted_netsuite": number | null,"posted_quickbooks": number | null,"tolerance_abs": number | null,"tolerance_pct": number | null,"vendor_resolved": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"v_status_bar": {
                  Row: {
                    "avg_decision_seconds_today": number | null,"dead_letters_open": number | null,"erp_failing": Json | null,"exceptions_cleared_today": number | null,"exceptions_open": number | null,"exceptions_raised_today": number | null,"last_autosave_at": string | null,"last_run_at": string | null,"mv_refreshed_at": string | null,"org_id": string | null,"payments_blocked": number | null,"pipeline_paused_reason": string | null,"review_queue_size": number | null,"runs_today": number | null,"workflow_version": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                }
          }
          Functions: {
            "audit_row_digest":
{ Args: { "p_action": string,"p_actor_id": string,"p_actor_type": Database["public"]['Enums']["actor_type"],"p_after": Json,"p_at": string,"p_before": Json,"p_entity_id": string,"p_entity_type": string,"p_org": string,"p_prev": string }; Returns: string
                           },
"audit_verify":
{ Args: { "p_org": string }; Returns: number
                           },
"audit_verify_org":
{ Args: { "p_org": string }; Returns: Json
                           },
"audit_write":
{ Args: { "p_action": string,"p_actor_id": string,"p_actor_type": Database["public"]['Enums']["actor_type"],"p_after": Json,"p_before": Json,"p_entity_id": string,"p_entity_type": string,"p_org": string }; Returns: number
                           },
"decision_action_label":
{ Args: { "p": Database["public"]['Enums']["decision_action"] }; Returns: string
                           },
"demo_purge_org":
{ Args: { "p_keep_master"?: boolean,"p_org": string }; Returns: Json
                           },
"exception_group_label":
{ Args: { "p": Database["public"]['Enums']["exception_type"] }; Returns: string
                           },
"exception_status_label":
{ Args: { "p": Database["public"]['Enums']["exception_type"] }; Returns: string
                           },
"has_role":
{ Args: { "p_org": string,"roles": (Database["public"]['Enums']["member_role"])[] }; Returns: boolean
                           },
"is_member":
{ Args: { "p_org": string }; Returns: boolean
                           },
"kb_search":
{ Args: { "p_k"?: number,"p_kinds"?: (string)[],"p_org": string,"p_query_embedding": string,"p_query_text": string }; Returns: {
              "chunk_id": string,"clause_ref": string,"content": string,"contract_id": string,"document_id": string,"heading_path": string,"kind": string,"rrf_score": number,"text_rank": number,"title": string,"vector_rank": number,"vendor_id": string
            }[]
                           },
"ledgic_actor_type":
{ Args: Record<PropertyKey, never>; Returns: Database["public"]['Enums']["actor_type"]
                           },
"ledgic_error":
{ Args: { "p_code": string,"p_msg": string }; Returns: undefined
                           },
"ledgic_is_service":
{ Args: Record<PropertyKey, never>; Returns: boolean
                           },
"ledgic_money":
{ Args: { "p": number }; Returns: string
                           },
"ledgic_parse_amount":
{ Args: { "p_allow_zero"?: boolean,"p_label": string,"p_value": string }; Returns: number
                           },
"ledgic_parse_date":
{ Args: { "p_label": string,"p_value": string }; Returns: string
                           },
"ledgic_resume_run":
{ Args: { "p_actor": string,"p_decision": Json,"p_event_stage": Database["public"]['Enums']["stage"],"p_exception": Omit<Database["public"]['Tables']["exceptions"]['Row'], Database["public"]['Tables']["exceptions"]['ComputedFields']>,"p_next_stage": Database["public"]['Enums']["stage"],"p_summary": string,"p_wake": boolean }; Returns: string
                           },
"ledgic_try_numeric":
{ Args: { "p": string }; Returns: number
                           },
"llm_budget_release_stale":
{ Args: Record<PropertyKey, never>; Returns: number
                           },
"llm_budget_reserve":
{ Args: { "p_cap"?: number,"p_est": number }; Returns: string
                           },
"llm_budget_settle":
{ Args: { "p_actual": number,"p_reservation": string }; Returns: undefined
                           },
"member_role_of":
{ Args: { "p_org": string }; Returns: Database["public"]['Enums']["member_role"]
                           },
"rate_limit_hit":
{ Args: { "p_key": string,"p_limit": number,"p_window_seconds": number }; Returns: boolean
                           },
"refresh_kpis":
{ Args: Record<PropertyKey, never>; Returns: undefined
                           },
"role_rank":
{ Args: { "p_role": Database["public"]['Enums']["member_role"] }; Returns: number
                           },
"rpc_confirm_fields":
{ Args: { "p_fields": Json,"p_invoice_id": string,"p_time_spent"?: number }; Returns: Json
                           },
"rpc_decide_exception":
{ Args: { "p_action": Database["public"]['Enums']["decision_action"],"p_comment"?: string,"p_exception_id": string,"p_extra"?: Json,"p_hold_amount"?: number,"p_pay_amount"?: number,"p_time_spent"?: number }; Returns: Json
                           },
"rpc_mark_exception_viewed":
{ Args: { "p_exception_id": string }; Returns: undefined
                           },
"shares_org":
{ Args: { "p_user": string }; Returns: boolean
                           },
"try_uuid":
{ Args: { "p": string }; Returns: string
                           }
          }
          Enums: {
            "actor_type": "system"|"user"|"core"|"agent"|"mcp","channel": "email"|"photo"|"portal"|"edi"|"upload","cost_kind": "llm"|"ocr"|"infra"|"human","decision_action": "confirm_fields"|"short_pay"|"approve_as_is"|"dispute"|"link_po"|"approve_without_po"|"merge"|"reject_copy"|"not_duplicate"|"request_w9"|"release_hold"|"reject_invoice"|"retry_posting","erp_system": "quickbooks"|"netsuite"|"none","event_status": "started"|"succeeded"|"failed"|"skipped"|"waiting"|"resumed","exception_status": "open"|"awaiting_vendor"|"disputed"|"resolved"|"escalated","exception_type": "extraction_review"|"price_variance"|"qty_mismatch"|"no_po"|"unmatched_line"|"duplicate"|"new_vendor_screen"|"posting_failed","field_source": "llm"|"ocr"|"edi"|"human"|"rule","invoice_status": "received"|"extracted"|"in_review"|"enriched"|"screened"|"matched"|"awaiting_decision"|"approved"|"posting"|"posted"|"rejected"|"duplicate"|"failed","invoice_verdict": "clean"|"price_variance"|"qty_mismatch"|"no_po"|"unmatched_line"|"mixed","line_verdict": "matched"|"price_variance"|"qty_over_receipt"|"qty_over_order"|"unmatched_line"|"favorable","match_mode": "three_way"|"two_way","member_role": "viewer"|"ap_clerk"|"ap_manager"|"controller"|"admin","stage": "intake"|"extraction"|"review"|"enrichment"|"screening"|"match"|"approval"|"posting"|"notify"|"close"
          }
          CompositeTypes: {
            [_ in never]: never
          }
        }
}

type DatabaseWithoutInternals = Omit<Database, '__InternalSupabase'>

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
  ? (DefaultSchema["Tables"] & DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
      Row: infer R
    }
    ? R
    : never
  : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
  ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
      Insert: infer I
    }
    ? I
    : never
  : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
  ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
      Update: infer U
    }
    ? U
    : never
  : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never
> = DefaultSchemaEnumNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
  ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
  : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never
> = PublicCompositeTypeNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
  ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
  : never

export const Constants = {
  "graphql_public": {
          Enums: {
            
          }
        },"public": {
          Enums: {
            "actor_type": ["system", "user", "core", "agent", "mcp"],"channel": ["email", "photo", "portal", "edi", "upload"],"cost_kind": ["llm", "ocr", "infra", "human"],"decision_action": ["confirm_fields", "short_pay", "approve_as_is", "dispute", "link_po", "approve_without_po", "merge", "reject_copy", "not_duplicate", "request_w9", "release_hold", "reject_invoice", "retry_posting"],"erp_system": ["quickbooks", "netsuite", "none"],"event_status": ["started", "succeeded", "failed", "skipped", "waiting", "resumed"],"exception_status": ["open", "awaiting_vendor", "disputed", "resolved", "escalated"],"exception_type": ["extraction_review", "price_variance", "qty_mismatch", "no_po", "unmatched_line", "duplicate", "new_vendor_screen", "posting_failed"],"field_source": ["llm", "ocr", "edi", "human", "rule"],"invoice_status": ["received", "extracted", "in_review", "enriched", "screened", "matched", "awaiting_decision", "approved", "posting", "posted", "rejected", "duplicate", "failed"],"invoice_verdict": ["clean", "price_variance", "qty_mismatch", "no_po", "unmatched_line", "mixed"],"line_verdict": ["matched", "price_variance", "qty_over_receipt", "qty_over_order", "unmatched_line", "favorable"],"match_mode": ["three_way", "two_way"],"member_role": ["viewer", "ap_clerk", "ap_manager", "controller", "admin"],"stage": ["intake", "extraction", "review", "enrichment", "screening", "match", "approval", "posting", "notify", "close"]
          }
        }
} as const
