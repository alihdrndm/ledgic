export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export type Database = {
  graphql_public: {
    Tables: {
      [_ in never]: never;
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      graphql: {
        Args: {
          extensions?: Json;
          operationName?: string;
          query?: string;
          variables?: Json;
        };
        Returns: Json;
      };
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
  public: {
    Tables: {
      approvals: {
        Row: {
          action: Database["public"]["Enums"]["decision_action"];
          actor_id: string;
          comment: string | null;
          decided_at: string;
          exception_id: string;
          hold_amount: number | null;
          id: string;
          org_id: string;
          pay_amount: number | null;
          time_spent_seconds: number | null;
        };
        ComputedFields: never;
        Insert: {
          action: Database["public"]["Enums"]["decision_action"];
          actor_id: string;
          comment?: string | null;
          decided_at?: string;
          exception_id: string;
          hold_amount?: number | null;
          id?: string;
          org_id: string;
          pay_amount?: number | null;
          time_spent_seconds?: number | null;
        };
        Update: {
          action?: Database["public"]["Enums"]["decision_action"];
          actor_id?: string;
          comment?: string | null;
          decided_at?: string;
          exception_id?: string;
          hold_amount?: number | null;
          id?: string;
          org_id?: string;
          pay_amount?: number | null;
          time_spent_seconds?: number | null;
        };
        Relationships: [
          {
            foreignKeyName: "approvals_exception_id_fkey";
            columns: ["exception_id"];
            isOneToOne: false;
            referencedRelation: "exceptions";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "approvals_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      audit_log: {
        Row: {
          action: string;
          actor_id: string | null;
          actor_type: Database["public"]["Enums"]["actor_type"];
          after: Json | null;
          at: string;
          before: Json | null;
          entity_id: string;
          entity_type: string;
          hash: string;
          id: number;
          org_id: string;
          prev_hash: string | null;
        };
        ComputedFields: never;
        Insert: {
          action: string;
          actor_id?: string | null;
          actor_type: Database["public"]["Enums"]["actor_type"];
          after?: Json | null;
          at?: string;
          before?: Json | null;
          entity_id: string;
          entity_type: string;
          hash: string;
          id?: number;
          org_id: string;
          prev_hash?: string | null;
        };
        Update: {
          action?: string;
          actor_id?: string | null;
          actor_type?: Database["public"]["Enums"]["actor_type"];
          after?: Json | null;
          at?: string;
          before?: Json | null;
          entity_id?: string;
          entity_type?: string;
          hash?: string;
          id?: number;
          org_id?: string;
          prev_hash?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "audit_log_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      contract_prices: {
        Row: {
          clause_ref: string;
          contract_id: string;
          id: string;
          item_id: string;
          unit_price: number;
          uom: string;
        };
        ComputedFields: never;
        Insert: {
          clause_ref: string;
          contract_id: string;
          id?: string;
          item_id: string;
          unit_price: number;
          uom: string;
        };
        Update: {
          clause_ref?: string;
          contract_id?: string;
          id?: string;
          item_id?: string;
          unit_price?: number;
          uom?: string;
        };
        Relationships: [
          {
            foreignKeyName: "contract_prices_contract_id_fkey";
            columns: ["contract_id"];
            isOneToOne: false;
            referencedRelation: "contracts";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "contract_prices_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
        ];
      };
      contracts: {
        Row: {
          countersigned_at: string | null;
          document_path: string | null;
          effective_from: string;
          effective_to: string;
          id: string;
          org_id: string;
          title: string;
          vendor_id: string;
        };
        ComputedFields: never;
        Insert: {
          countersigned_at?: string | null;
          document_path?: string | null;
          effective_from: string;
          effective_to: string;
          id?: string;
          org_id: string;
          title: string;
          vendor_id: string;
        };
        Update: {
          countersigned_at?: string | null;
          document_path?: string | null;
          effective_from?: string;
          effective_to?: string;
          id?: string;
          org_id?: string;
          title?: string;
          vendor_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "contracts_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "contracts_vendor_id_fkey";
            columns: ["vendor_id"];
            isOneToOne: false;
            referencedRelation: "vendors";
            referencedColumns: ["id"];
          },
        ];
      };
      copilot_cache: {
        Row: {
          answer: NonNullable<Json>;
          created_at: string;
          org_id: string;
          q_hash: string;
          question: string;
        };
        ComputedFields: never;
        Insert: {
          answer: NonNullable<Json>;
          created_at?: string;
          org_id: string;
          q_hash: string;
          question: string;
        };
        Update: {
          answer?: NonNullable<Json>;
          created_at?: string;
          org_id?: string;
          q_hash?: string;
          question?: string;
        };
        Relationships: [
          {
            foreignKeyName: "copilot_cache_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      cost_ledger: {
        Row: {
          amount_usd: number;
          at: string;
          id: number;
          kind: Database["public"]["Enums"]["cost_kind"];
          meta: NonNullable<Json>;
          org_id: string;
          run_id: string | null;
        };
        ComputedFields: never;
        Insert: {
          amount_usd: number;
          at?: string;
          id?: number;
          kind: Database["public"]["Enums"]["cost_kind"];
          meta?: NonNullable<Json>;
          org_id: string;
          run_id?: string | null;
        };
        Update: {
          amount_usd?: number;
          at?: string;
          id?: number;
          kind?: Database["public"]["Enums"]["cost_kind"];
          meta?: NonNullable<Json>;
          org_id?: string;
          run_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "cost_ledger_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "cost_ledger_run_id_fkey";
            columns: ["run_id"];
            isOneToOne: false;
            referencedRelation: "pipeline_runs";
            referencedColumns: ["id"];
          },
        ];
      };
      dead_letters: {
        Row: {
          created_at: string;
          error: string;
          id: string;
          org_id: string | null;
          payload: Json | null;
          resolved_at: string | null;
          run_id: string | null;
          stage: Database["public"]["Enums"]["stage"] | null;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          error: string;
          id?: string;
          org_id?: string | null;
          payload?: Json | null;
          resolved_at?: string | null;
          run_id?: string | null;
          stage?: Database["public"]["Enums"]["stage"] | null;
        };
        Update: {
          created_at?: string;
          error?: string;
          id?: string;
          org_id?: string | null;
          payload?: Json | null;
          resolved_at?: string | null;
          run_id?: string | null;
          stage?: Database["public"]["Enums"]["stage"] | null;
        };
        Relationships: [
          {
            foreignKeyName: "dead_letters_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "dead_letters_run_id_fkey";
            columns: ["run_id"];
            isOneToOne: false;
            referencedRelation: "pipeline_runs";
            referencedColumns: ["id"];
          },
        ];
      };
      documents: {
        Row: {
          channel: Database["public"]["Enums"]["channel"];
          id: string;
          mime: string;
          org_id: string;
          original_filename: string | null;
          page_count: number | null;
          phash: string | null;
          preprocessing: Json | null;
          received_at: string;
          sha256: string;
          source_meta: NonNullable<Json>;
          storage_path: string;
        };
        ComputedFields: never;
        Insert: {
          channel: Database["public"]["Enums"]["channel"];
          id?: string;
          mime: string;
          org_id: string;
          original_filename?: string | null;
          page_count?: number | null;
          phash?: string | null;
          preprocessing?: Json | null;
          received_at?: string;
          sha256: string;
          source_meta?: NonNullable<Json>;
          storage_path: string;
        };
        Update: {
          channel?: Database["public"]["Enums"]["channel"];
          id?: string;
          mime?: string;
          org_id?: string;
          original_filename?: string | null;
          page_count?: number | null;
          phash?: string | null;
          preprocessing?: Json | null;
          received_at?: string;
          sha256?: string;
          source_meta?: NonNullable<Json>;
          storage_path?: string;
        };
        Relationships: [
          {
            foreignKeyName: "documents_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      duplicate_candidates: {
        Row: {
          candidate_invoice_id: string;
          created_at: string;
          evidence: NonNullable<Json>;
          id: string;
          invoice_id: string;
          org_id: string;
          similarity: number;
        };
        ComputedFields: never;
        Insert: {
          candidate_invoice_id: string;
          created_at?: string;
          evidence: NonNullable<Json>;
          id?: string;
          invoice_id: string;
          org_id: string;
          similarity: number;
        };
        Update: {
          candidate_invoice_id?: string;
          created_at?: string;
          evidence?: NonNullable<Json>;
          id?: string;
          invoice_id?: string;
          org_id?: string;
          similarity?: number;
        };
        Relationships: [
          {
            foreignKeyName: "duplicate_candidates_candidate_invoice_id_fkey";
            columns: ["candidate_invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "duplicate_candidates_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "duplicate_candidates_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      entities: {
        Row: {
          erp: Database["public"]["Enums"]["erp_system"];
          erp_company_ref: string | null;
          id: string;
          name: string;
          org_id: string;
          short_code: string;
        };
        ComputedFields: never;
        Insert: {
          erp: Database["public"]["Enums"]["erp_system"];
          erp_company_ref?: string | null;
          id?: string;
          name: string;
          org_id: string;
          short_code: string;
        };
        Update: {
          erp?: Database["public"]["Enums"]["erp_system"];
          erp_company_ref?: string | null;
          id?: string;
          name?: string;
          org_id?: string;
          short_code?: string;
        };
        Relationships: [
          {
            foreignKeyName: "entities_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      erp_postings: {
        Row: {
          attempts: number;
          error: string | null;
          external_id: string | null;
          id: string;
          invoice_id: string;
          org_id: string;
          posted_at: string | null;
          request: NonNullable<Json>;
          response: Json | null;
          status: string;
          system: Database["public"]["Enums"]["erp_system"];
        };
        ComputedFields: never;
        Insert: {
          attempts?: number;
          error?: string | null;
          external_id?: string | null;
          id?: string;
          invoice_id: string;
          org_id: string;
          posted_at?: string | null;
          request: NonNullable<Json>;
          response?: Json | null;
          status: string;
          system: Database["public"]["Enums"]["erp_system"];
        };
        Update: {
          attempts?: number;
          error?: string | null;
          external_id?: string | null;
          id?: string;
          invoice_id?: string;
          org_id?: string;
          posted_at?: string | null;
          request?: NonNullable<Json>;
          response?: Json | null;
          status?: string;
          system?: Database["public"]["Enums"]["erp_system"];
        };
        Relationships: [
          {
            foreignKeyName: "erp_postings_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "erp_postings_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      eval_runs: {
        Row: {
          accuracy: number | null;
          by_field: NonNullable<Json>;
          created_at: string;
          fields_correct: number;
          fields_labeled: number;
          id: string;
          org_id: string | null;
          prompt_version: string | null;
          sample_size: number;
          week_start: string;
        };
        ComputedFields: never;
        Insert: {
          accuracy?: never;
          by_field: NonNullable<Json>;
          created_at?: string;
          fields_correct: number;
          fields_labeled: number;
          id?: string;
          org_id?: string | null;
          prompt_version?: string | null;
          sample_size: number;
          week_start: string;
        };
        Update: {
          accuracy?: never;
          by_field?: NonNullable<Json>;
          created_at?: string;
          fields_correct?: number;
          fields_labeled?: number;
          id?: string;
          org_id?: string | null;
          prompt_version?: string | null;
          sample_size?: number;
          week_start?: string;
        };
        Relationships: [
          {
            foreignKeyName: "eval_runs_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "eval_runs_prompt_version_fkey";
            columns: ["prompt_version"];
            isOneToOne: false;
            referencedRelation: "prompt_versions";
            referencedColumns: ["id"];
          },
        ];
      };
      exception_drafts: {
        Row: {
          body_md: string;
          citations: NonNullable<Json>;
          cost_usd: number;
          created_at: string;
          exception_id: string;
          id: string;
          kind: string;
          mode: string;
          model: string | null;
          org_id: string;
          prompt_version: string | null;
        };
        ComputedFields: never;
        Insert: {
          body_md: string;
          citations?: NonNullable<Json>;
          cost_usd?: number;
          created_at?: string;
          exception_id: string;
          id?: string;
          kind: string;
          mode: string;
          model?: string | null;
          org_id: string;
          prompt_version?: string | null;
        };
        Update: {
          body_md?: string;
          citations?: NonNullable<Json>;
          cost_usd?: number;
          created_at?: string;
          exception_id?: string;
          id?: string;
          kind?: string;
          mode?: string;
          model?: string | null;
          org_id?: string;
          prompt_version?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "exception_drafts_exception_id_fkey";
            columns: ["exception_id"];
            isOneToOne: false;
            referencedRelation: "exceptions";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "exception_drafts_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      exceptions: {
        Row: {
          amount_at_risk: number;
          assigned_role: Database["public"]["Enums"]["member_role"];
          assigned_to: string | null;
          escalated: boolean;
          first_viewed_at: string | null;
          id: string;
          invoice_id: string;
          opened_at: string;
          org_id: string;
          reason: string;
          resolved_at: string | null;
          run_id: string | null;
          sla_due_at: string;
          status: Database["public"]["Enums"]["exception_status"];
          type: Database["public"]["Enums"]["exception_type"];
        };
        ComputedFields: never;
        Insert: {
          amount_at_risk?: number;
          assigned_role?: Database["public"]["Enums"]["member_role"];
          assigned_to?: string | null;
          escalated?: boolean;
          first_viewed_at?: string | null;
          id?: string;
          invoice_id: string;
          opened_at?: string;
          org_id: string;
          reason: string;
          resolved_at?: string | null;
          run_id?: string | null;
          sla_due_at: string;
          status?: Database["public"]["Enums"]["exception_status"];
          type: Database["public"]["Enums"]["exception_type"];
        };
        Update: {
          amount_at_risk?: number;
          assigned_role?: Database["public"]["Enums"]["member_role"];
          assigned_to?: string | null;
          escalated?: boolean;
          first_viewed_at?: string | null;
          id?: string;
          invoice_id?: string;
          opened_at?: string;
          org_id?: string;
          reason?: string;
          resolved_at?: string | null;
          run_id?: string | null;
          sla_due_at?: string;
          status?: Database["public"]["Enums"]["exception_status"];
          type?: Database["public"]["Enums"]["exception_type"];
        };
        Relationships: [
          {
            foreignKeyName: "exceptions_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "exceptions_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "exceptions_run_id_fkey";
            columns: ["run_id"];
            isOneToOne: false;
            referencedRelation: "pipeline_runs";
            referencedColumns: ["id"];
          },
        ];
      };
      fraud_signals: {
        Row: {
          created_at: string;
          detail: NonNullable<Json>;
          id: string;
          invoice_id: string;
          org_id: string;
          signal: string;
          vendor_id: string | null;
          weight: number;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          detail?: NonNullable<Json>;
          id?: string;
          invoice_id: string;
          org_id: string;
          signal: string;
          vendor_id?: string | null;
          weight: number;
        };
        Update: {
          created_at?: string;
          detail?: NonNullable<Json>;
          id?: string;
          invoice_id?: string;
          org_id?: string;
          signal?: string;
          vendor_id?: string | null;
          weight?: number;
        };
        Relationships: [
          {
            foreignKeyName: "fraud_signals_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "fraud_signals_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "fraud_signals_vendor_id_fkey";
            columns: ["vendor_id"];
            isOneToOne: false;
            referencedRelation: "vendors";
            referencedColumns: ["id"];
          },
        ];
      };
      gl_accounts: {
        Row: {
          entity_id: string | null;
          erp_ref: string | null;
          id: string;
          name: string;
          number: string;
          org_id: string;
        };
        ComputedFields: never;
        Insert: {
          entity_id?: string | null;
          erp_ref?: string | null;
          id?: string;
          name: string;
          number: string;
          org_id: string;
        };
        Update: {
          entity_id?: string | null;
          erp_ref?: string | null;
          id?: string;
          name?: string;
          number?: string;
          org_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "gl_accounts_entity_id_fkey";
            columns: ["entity_id"];
            isOneToOne: false;
            referencedRelation: "entities";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "gl_accounts_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      goods_receipts: {
        Row: {
          grn_number: string;
          id: string;
          org_id: string;
          po_id: string;
          received_at: string;
          received_by: string | null;
          source: string;
        };
        ComputedFields: never;
        Insert: {
          grn_number: string;
          id?: string;
          org_id: string;
          po_id: string;
          received_at: string;
          received_by?: string | null;
          source?: string;
        };
        Update: {
          grn_number?: string;
          id?: string;
          org_id?: string;
          po_id?: string;
          received_at?: string;
          received_by?: string | null;
          source?: string;
        };
        Relationships: [
          {
            foreignKeyName: "goods_receipts_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "goods_receipts_po_id_fkey";
            columns: ["po_id"];
            isOneToOne: false;
            referencedRelation: "purchase_orders";
            referencedColumns: ["id"];
          },
        ];
      };
      grn_lines: {
        Row: {
          grn_id: string;
          id: string;
          po_line_id: string;
          qty_received: number;
          uom: string;
        };
        ComputedFields: never;
        Insert: {
          grn_id: string;
          id?: string;
          po_line_id: string;
          qty_received: number;
          uom: string;
        };
        Update: {
          grn_id?: string;
          id?: string;
          po_line_id?: string;
          qty_received?: number;
          uom?: string;
        };
        Relationships: [
          {
            foreignKeyName: "grn_lines_grn_id_fkey";
            columns: ["grn_id"];
            isOneToOne: false;
            referencedRelation: "goods_receipts";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "grn_lines_po_line_id_fkey";
            columns: ["po_line_id"];
            isOneToOne: false;
            referencedRelation: "po_lines";
            referencedColumns: ["id"];
          },
        ];
      };
      integrations: {
        Row: {
          config: NonNullable<Json>;
          entity_id: string | null;
          id: string;
          last_error: string | null;
          last_sync_at: string | null;
          org_id: string;
          provider: string;
          status: string;
          vault_secret_id: string | null;
        };
        ComputedFields: never;
        Insert: {
          config?: NonNullable<Json>;
          entity_id?: string | null;
          id?: string;
          last_error?: string | null;
          last_sync_at?: string | null;
          org_id: string;
          provider: string;
          status?: string;
          vault_secret_id?: string | null;
        };
        Update: {
          config?: NonNullable<Json>;
          entity_id?: string | null;
          id?: string;
          last_error?: string | null;
          last_sync_at?: string | null;
          org_id?: string;
          provider?: string;
          status?: string;
          vault_secret_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "integrations_entity_id_fkey";
            columns: ["entity_id"];
            isOneToOne: false;
            referencedRelation: "entities";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "integrations_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      invoice_fields: {
        Row: {
          bbox: Json | null;
          confidence: number;
          field: string;
          id: string;
          invoice_id: string;
          raw_confidence: number | null;
          set_at: string;
          set_by: string | null;
          source: Database["public"]["Enums"]["field_source"];
          value: string | null;
          version: number;
        };
        ComputedFields: never;
        Insert: {
          bbox?: Json | null;
          confidence: number;
          field: string;
          id?: string;
          invoice_id: string;
          raw_confidence?: number | null;
          set_at?: string;
          set_by?: string | null;
          source: Database["public"]["Enums"]["field_source"];
          value?: string | null;
          version?: number;
        };
        Update: {
          bbox?: Json | null;
          confidence?: number;
          field?: string;
          id?: string;
          invoice_id?: string;
          raw_confidence?: number | null;
          set_at?: string;
          set_by?: string | null;
          source?: Database["public"]["Enums"]["field_source"];
          value?: string | null;
          version?: number;
        };
        Relationships: [
          {
            foreignKeyName: "invoice_fields_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
        ];
      };
      invoice_lines: {
        Row: {
          amount: number | null;
          bboxes: Json | null;
          confidences: NonNullable<Json>;
          description: string;
          gl_account_id: string | null;
          gl_confidence: number | null;
          id: string;
          invoice_id: string;
          item_id: string | null;
          line_no: number;
          po_line_id: string | null;
          qty: number | null;
          unit_price: number | null;
          uom: string | null;
        };
        ComputedFields: never;
        Insert: {
          amount?: number | null;
          bboxes?: Json | null;
          confidences: NonNullable<Json>;
          description: string;
          gl_account_id?: string | null;
          gl_confidence?: number | null;
          id?: string;
          invoice_id: string;
          item_id?: string | null;
          line_no: number;
          po_line_id?: string | null;
          qty?: number | null;
          unit_price?: number | null;
          uom?: string | null;
        };
        Update: {
          amount?: number | null;
          bboxes?: Json | null;
          confidences?: NonNullable<Json>;
          description?: string;
          gl_account_id?: string | null;
          gl_confidence?: number | null;
          id?: string;
          invoice_id?: string;
          item_id?: string | null;
          line_no?: number;
          po_line_id?: string | null;
          qty?: number | null;
          unit_price?: number | null;
          uom?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "invoice_lines_gl_account_id_fkey";
            columns: ["gl_account_id"];
            isOneToOne: false;
            referencedRelation: "gl_accounts";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoice_lines_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoice_lines_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoice_lines_po_line_id_fkey";
            columns: ["po_line_id"];
            isOneToOne: false;
            referencedRelation: "po_lines";
            referencedColumns: ["id"];
          },
        ];
      };
      invoices: {
        Row: {
          created_at: string;
          currency: string;
          doc_confidence: number | null;
          document_id: string;
          due_date: string | null;
          duplicate_of: string | null;
          entity_id: string | null;
          extraction_mode: string | null;
          freight: number | null;
          gate_passed: boolean | null;
          human_touches: number;
          id: string;
          invoice_date: string | null;
          invoice_number: string | null;
          invoice_number_norm: string | null;
          location_id: string | null;
          org_id: string;
          po_id: string | null;
          posted_at: string | null;
          received_at: string;
          status: Database["public"]["Enums"]["invoice_status"];
          subtotal: number | null;
          tax: number | null;
          terms: string | null;
          total: number | null;
          touchless: boolean | null;
          vendor_id: string | null;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          currency?: string;
          doc_confidence?: number | null;
          document_id: string;
          due_date?: string | null;
          duplicate_of?: string | null;
          entity_id?: string | null;
          extraction_mode?: string | null;
          freight?: number | null;
          gate_passed?: boolean | null;
          human_touches?: number;
          id?: string;
          invoice_date?: string | null;
          invoice_number?: string | null;
          invoice_number_norm?: never;
          location_id?: string | null;
          org_id: string;
          po_id?: string | null;
          posted_at?: string | null;
          received_at: string;
          status?: Database["public"]["Enums"]["invoice_status"];
          subtotal?: number | null;
          tax?: number | null;
          terms?: string | null;
          total?: number | null;
          touchless?: boolean | null;
          vendor_id?: string | null;
        };
        Update: {
          created_at?: string;
          currency?: string;
          doc_confidence?: number | null;
          document_id?: string;
          due_date?: string | null;
          duplicate_of?: string | null;
          entity_id?: string | null;
          extraction_mode?: string | null;
          freight?: number | null;
          gate_passed?: boolean | null;
          human_touches?: number;
          id?: string;
          invoice_date?: string | null;
          invoice_number?: string | null;
          invoice_number_norm?: never;
          location_id?: string | null;
          org_id?: string;
          po_id?: string | null;
          posted_at?: string | null;
          received_at?: string;
          status?: Database["public"]["Enums"]["invoice_status"];
          subtotal?: number | null;
          tax?: number | null;
          terms?: string | null;
          total?: number | null;
          touchless?: boolean | null;
          vendor_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "invoices_document_id_fkey";
            columns: ["document_id"];
            isOneToOne: false;
            referencedRelation: "documents";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoices_duplicate_of_fkey";
            columns: ["duplicate_of"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoices_entity_id_fkey";
            columns: ["entity_id"];
            isOneToOne: false;
            referencedRelation: "entities";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoices_location_id_fkey";
            columns: ["location_id"];
            isOneToOne: false;
            referencedRelation: "locations";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoices_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoices_po_id_fkey";
            columns: ["po_id"];
            isOneToOne: false;
            referencedRelation: "purchase_orders";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "invoices_vendor_id_fkey";
            columns: ["vendor_id"];
            isOneToOne: false;
            referencedRelation: "vendors";
            referencedColumns: ["id"];
          },
        ];
      };
      items: {
        Row: {
          default_gl: string | null;
          description: string;
          embedding: string | null;
          id: string;
          item_key: string;
          org_id: string;
          uom: string;
        };
        ComputedFields: never;
        Insert: {
          default_gl?: string | null;
          description: string;
          embedding?: string | null;
          id?: string;
          item_key: string;
          org_id: string;
          uom: string;
        };
        Update: {
          default_gl?: string | null;
          description?: string;
          embedding?: string | null;
          id?: string;
          item_key?: string;
          org_id?: string;
          uom?: string;
        };
        Relationships: [
          {
            foreignKeyName: "items_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      kb_chunks: {
        Row: {
          clause_ref: string | null;
          content: string;
          document_id: string;
          embedding: string | null;
          heading_path: string | null;
          id: string;
          ord: number;
          org_id: string;
          tsv: unknown;
        };
        ComputedFields: never;
        Insert: {
          clause_ref?: string | null;
          content: string;
          document_id: string;
          embedding?: string | null;
          heading_path?: string | null;
          id?: string;
          ord: number;
          org_id: string;
          tsv?: never;
        };
        Update: {
          clause_ref?: string | null;
          content?: string;
          document_id?: string;
          embedding?: string | null;
          heading_path?: string | null;
          id?: string;
          ord?: number;
          org_id?: string;
          tsv?: never;
        };
        Relationships: [
          {
            foreignKeyName: "kb_chunks_document_id_fkey";
            columns: ["document_id"];
            isOneToOne: false;
            referencedRelation: "kb_documents";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "kb_chunks_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      kb_documents: {
        Row: {
          contract_id: string | null;
          created_at: string;
          id: string;
          kind: string;
          org_id: string;
          source_path: string | null;
          title: string;
          vendor_id: string | null;
        };
        ComputedFields: never;
        Insert: {
          contract_id?: string | null;
          created_at?: string;
          id?: string;
          kind: string;
          org_id: string;
          source_path?: string | null;
          title: string;
          vendor_id?: string | null;
        };
        Update: {
          contract_id?: string | null;
          created_at?: string;
          id?: string;
          kind?: string;
          org_id?: string;
          source_path?: string | null;
          title?: string;
          vendor_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "kb_documents_contract_id_fkey";
            columns: ["contract_id"];
            isOneToOne: false;
            referencedRelation: "contracts";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "kb_documents_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "kb_documents_vendor_id_fkey";
            columns: ["vendor_id"];
            isOneToOne: false;
            referencedRelation: "vendors";
            referencedColumns: ["id"];
          },
        ];
      };
      llm_budget: {
        Row: {
          cap_usd: number;
          day: string;
          reserved_usd: number;
          spent_usd: number;
        };
        ComputedFields: never;
        Insert: {
          cap_usd: number;
          day: string;
          reserved_usd?: number;
          spent_usd?: number;
        };
        Update: {
          cap_usd?: number;
          day?: string;
          reserved_usd?: number;
          spent_usd?: number;
        };
        Relationships: [];
      };
      llm_budget_reservations: {
        Row: {
          actual_usd: number | null;
          created_at: string;
          day: string;
          est_usd: number;
          id: string;
          settled_at: string | null;
          status: string;
        };
        ComputedFields: never;
        Insert: {
          actual_usd?: number | null;
          created_at?: string;
          day: string;
          est_usd: number;
          id?: string;
          settled_at?: string | null;
          status?: string;
        };
        Update: {
          actual_usd?: number | null;
          created_at?: string;
          day?: string;
          est_usd?: number;
          id?: string;
          settled_at?: string | null;
          status?: string;
        };
        Relationships: [
          {
            foreignKeyName: "llm_budget_reservations_day_fkey";
            columns: ["day"];
            isOneToOne: false;
            referencedRelation: "llm_budget";
            referencedColumns: ["day"];
          },
        ];
      };
      locations: {
        Row: {
          code: string;
          entity_id: string;
          erp_class_ref: string | null;
          id: string;
          name: string;
          org_id: string;
        };
        ComputedFields: never;
        Insert: {
          code: string;
          entity_id: string;
          erp_class_ref?: string | null;
          id?: string;
          name: string;
          org_id: string;
        };
        Update: {
          code?: string;
          entity_id?: string;
          erp_class_ref?: string | null;
          id?: string;
          name?: string;
          org_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "locations_entity_id_fkey";
            columns: ["entity_id"];
            isOneToOne: false;
            referencedRelation: "entities";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "locations_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      match_line_results: {
        Row: {
          allowed_amount: number | null;
          contract_price_id: string | null;
          delta_amount: number | null;
          delta_pct: number | null;
          expected_amount: number | null;
          expected_source: string | null;
          expected_unit_price: number | null;
          grn_qty: number | null;
          id: string;
          invoice_line_id: string;
          match_result_id: string;
          note: string | null;
          po_line_id: string | null;
          verdict: Database["public"]["Enums"]["line_verdict"];
        };
        ComputedFields: never;
        Insert: {
          allowed_amount?: number | null;
          contract_price_id?: string | null;
          delta_amount?: number | null;
          delta_pct?: number | null;
          expected_amount?: number | null;
          expected_source?: string | null;
          expected_unit_price?: number | null;
          grn_qty?: number | null;
          id?: string;
          invoice_line_id: string;
          match_result_id: string;
          note?: string | null;
          po_line_id?: string | null;
          verdict: Database["public"]["Enums"]["line_verdict"];
        };
        Update: {
          allowed_amount?: number | null;
          contract_price_id?: string | null;
          delta_amount?: number | null;
          delta_pct?: number | null;
          expected_amount?: number | null;
          expected_source?: string | null;
          expected_unit_price?: number | null;
          grn_qty?: number | null;
          id?: string;
          invoice_line_id?: string;
          match_result_id?: string;
          note?: string | null;
          po_line_id?: string | null;
          verdict?: Database["public"]["Enums"]["line_verdict"];
        };
        Relationships: [
          {
            foreignKeyName: "match_line_results_contract_price_id_fkey";
            columns: ["contract_price_id"];
            isOneToOne: false;
            referencedRelation: "contract_prices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "match_line_results_invoice_line_id_fkey";
            columns: ["invoice_line_id"];
            isOneToOne: false;
            referencedRelation: "invoice_lines";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "match_line_results_match_result_id_fkey";
            columns: ["match_result_id"];
            isOneToOne: false;
            referencedRelation: "match_results";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "match_line_results_po_line_id_fkey";
            columns: ["po_line_id"];
            isOneToOne: false;
            referencedRelation: "po_lines";
            referencedColumns: ["id"];
          },
        ];
      };
      match_results: {
        Row: {
          computed_at: string;
          duration_ms: number;
          expected_total: number;
          id: string;
          invoice_id: string;
          lines_total: number;
          lines_verified: number;
          tolerance_abs: number;
          tolerance_pct: number;
          total_delta: number;
          verdict: Database["public"]["Enums"]["invoice_verdict"];
        };
        ComputedFields: never;
        Insert: {
          computed_at?: string;
          duration_ms: number;
          expected_total: number;
          id?: string;
          invoice_id: string;
          lines_total: number;
          lines_verified: number;
          tolerance_abs: number;
          tolerance_pct: number;
          total_delta: number;
          verdict: Database["public"]["Enums"]["invoice_verdict"];
        };
        Update: {
          computed_at?: string;
          duration_ms?: number;
          expected_total?: number;
          id?: string;
          invoice_id?: string;
          lines_total?: number;
          lines_verified?: number;
          tolerance_abs?: number;
          tolerance_pct?: number;
          total_delta?: number;
          verdict?: Database["public"]["Enums"]["invoice_verdict"];
        };
        Relationships: [
          {
            foreignKeyName: "match_results_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: true;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
        ];
      };
      mcp_tokens: {
        Row: {
          created_at: string;
          id: string;
          last_used_at: string | null;
          name: string;
          org_id: string;
          revoked_at: string | null;
          scopes: string[];
          token_hash: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          id?: string;
          last_used_at?: string | null;
          name: string;
          org_id: string;
          revoked_at?: string | null;
          scopes?: string[];
          token_hash: string;
          user_id: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          last_used_at?: string | null;
          name?: string;
          org_id?: string;
          revoked_at?: string | null;
          scopes?: string[];
          token_hash?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "mcp_tokens_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      memberships: {
        Row: {
          created_at: string;
          org_id: string;
          role: Database["public"]["Enums"]["member_role"];
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          org_id: string;
          role: Database["public"]["Enums"]["member_role"];
          user_id: string;
        };
        Update: {
          created_at?: string;
          org_id?: string;
          role?: Database["public"]["Enums"]["member_role"];
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "memberships_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      org_settings: {
        Row: {
          confidence_gate: number;
          controller_notify_threshold: number;
          dup_hold_threshold: number;
          dup_suggest_threshold: number;
          field_floor: number;
          fraud_hold_threshold: number;
          infra_monthly_usd: number;
          loaded_hourly_rate_usd: number;
          manager_limit: number;
          org_id: string;
          over_receipt_allowance: number;
          sla_hours: number;
          slack_digest_local_time: string;
          updated_at: string;
        };
        ComputedFields: never;
        Insert: {
          confidence_gate?: number;
          controller_notify_threshold?: number;
          dup_hold_threshold?: number;
          dup_suggest_threshold?: number;
          field_floor?: number;
          fraud_hold_threshold?: number;
          infra_monthly_usd?: number;
          loaded_hourly_rate_usd?: number;
          manager_limit?: number;
          org_id: string;
          over_receipt_allowance?: number;
          sla_hours?: number;
          slack_digest_local_time?: string;
          updated_at?: string;
        };
        Update: {
          confidence_gate?: number;
          controller_notify_threshold?: number;
          dup_hold_threshold?: number;
          dup_suggest_threshold?: number;
          field_floor?: number;
          fraud_hold_threshold?: number;
          infra_monthly_usd?: number;
          loaded_hourly_rate_usd?: number;
          manager_limit?: number;
          org_id?: string;
          over_receipt_allowance?: number;
          sla_hours?: number;
          slack_digest_local_time?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: "org_settings_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: true;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      orgs: {
        Row: {
          created_at: string;
          id: string;
          is_demo: boolean;
          name: string;
          slug: string;
          timezone: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          id?: string;
          is_demo?: boolean;
          name: string;
          slug: string;
          timezone?: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          is_demo?: boolean;
          name?: string;
          slug?: string;
          timezone?: string;
        };
        Relationships: [];
      };
      pipeline_events: {
        Row: {
          at: string;
          detail: NonNullable<Json>;
          duration_ms: number | null;
          id: number;
          org_id: string;
          run_id: string;
          stage: Database["public"]["Enums"]["stage"];
          status: Database["public"]["Enums"]["event_status"];
          summary: string | null;
        };
        ComputedFields: never;
        Insert: {
          at?: string;
          detail?: NonNullable<Json>;
          duration_ms?: number | null;
          id?: number;
          org_id: string;
          run_id: string;
          stage: Database["public"]["Enums"]["stage"];
          status: Database["public"]["Enums"]["event_status"];
          summary?: string | null;
        };
        Update: {
          at?: string;
          detail?: NonNullable<Json>;
          duration_ms?: number | null;
          id?: number;
          org_id?: string;
          run_id?: string;
          stage?: Database["public"]["Enums"]["stage"];
          status?: Database["public"]["Enums"]["event_status"];
          summary?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "pipeline_events_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "pipeline_events_run_id_fkey";
            columns: ["run_id"];
            isOneToOne: false;
            referencedRelation: "pipeline_runs";
            referencedColumns: ["id"];
          },
        ];
      };
      pipeline_runs: {
        Row: {
          attempt: number;
          context: NonNullable<Json>;
          current_stage: Database["public"]["Enums"]["stage"];
          document_id: string;
          finished_at: string | null;
          id: string;
          invoice_id: string | null;
          last_error: string | null;
          lease_owner: string | null;
          lease_until: string | null;
          next_attempt_at: string | null;
          next_stage: Database["public"]["Enums"]["stage"] | null;
          orchestrator_version: string | null;
          org_id: string;
          run_number: number;
          started_at: string;
          status: string;
          wait_exception_id: string | null;
          workflow_version: string;
        };
        ComputedFields: never;
        Insert: {
          attempt?: number;
          context?: NonNullable<Json>;
          current_stage?: Database["public"]["Enums"]["stage"];
          document_id: string;
          finished_at?: string | null;
          id?: string;
          invoice_id?: string | null;
          last_error?: string | null;
          lease_owner?: string | null;
          lease_until?: string | null;
          next_attempt_at?: string | null;
          next_stage?: Database["public"]["Enums"]["stage"] | null;
          orchestrator_version?: string | null;
          org_id: string;
          run_number?: number;
          started_at?: string;
          status?: string;
          wait_exception_id?: string | null;
          workflow_version?: string;
        };
        Update: {
          attempt?: number;
          context?: NonNullable<Json>;
          current_stage?: Database["public"]["Enums"]["stage"];
          document_id?: string;
          finished_at?: string | null;
          id?: string;
          invoice_id?: string | null;
          last_error?: string | null;
          lease_owner?: string | null;
          lease_until?: string | null;
          next_attempt_at?: string | null;
          next_stage?: Database["public"]["Enums"]["stage"] | null;
          orchestrator_version?: string | null;
          org_id?: string;
          run_number?: number;
          started_at?: string;
          status?: string;
          wait_exception_id?: string | null;
          workflow_version?: string;
        };
        Relationships: [
          {
            foreignKeyName: "pipeline_runs_document_id_fkey";
            columns: ["document_id"];
            isOneToOne: false;
            referencedRelation: "documents";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "pipeline_runs_invoice_id_fkey";
            columns: ["invoice_id"];
            isOneToOne: false;
            referencedRelation: "invoices";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "pipeline_runs_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "pipeline_runs_wait_exception_fk";
            columns: ["wait_exception_id"];
            isOneToOne: false;
            referencedRelation: "exceptions";
            referencedColumns: ["id"];
          },
        ];
      };
      po_lines: {
        Row: {
          amount: number;
          description: string;
          id: string;
          item_id: string | null;
          line_no: number;
          po_id: string;
          qty: number;
          unit_price: number;
          uom: string;
        };
        ComputedFields: never;
        Insert: {
          amount: number;
          description: string;
          id?: string;
          item_id?: string | null;
          line_no: number;
          po_id: string;
          qty: number;
          unit_price: number;
          uom: string;
        };
        Update: {
          amount?: number;
          description?: string;
          id?: string;
          item_id?: string | null;
          line_no?: number;
          po_id?: string;
          qty?: number;
          unit_price?: number;
          uom?: string;
        };
        Relationships: [
          {
            foreignKeyName: "po_lines_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "po_lines_po_id_fkey";
            columns: ["po_id"];
            isOneToOne: false;
            referencedRelation: "purchase_orders";
            referencedColumns: ["id"];
          },
        ];
      };
      profiles: {
        Row: {
          created_at: string;
          full_name: string;
          initials: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          full_name: string;
          initials: string;
          user_id: string;
        };
        Update: {
          created_at?: string;
          full_name?: string;
          initials?: string;
          user_id?: string;
        };
        Relationships: [];
      };
      prompt_versions: {
        Row: {
          deployed_at: string;
          id: string;
          model: string;
          notes: string | null;
        };
        ComputedFields: never;
        Insert: {
          deployed_at: string;
          id: string;
          model: string;
          notes?: string | null;
        };
        Update: {
          deployed_at?: string;
          id?: string;
          model?: string;
          notes?: string | null;
        };
        Relationships: [];
      };
      purchase_orders: {
        Row: {
          entity_id: string;
          erp_ref: string | null;
          id: string;
          location_id: string;
          ordered_at: string;
          org_id: string;
          po_number: string;
          source: string;
          status: string;
          total: number;
          vendor_id: string;
        };
        ComputedFields: never;
        Insert: {
          entity_id: string;
          erp_ref?: string | null;
          id?: string;
          location_id: string;
          ordered_at: string;
          org_id: string;
          po_number: string;
          source?: string;
          status?: string;
          total: number;
          vendor_id: string;
        };
        Update: {
          entity_id?: string;
          erp_ref?: string | null;
          id?: string;
          location_id?: string;
          ordered_at?: string;
          org_id?: string;
          po_number?: string;
          source?: string;
          status?: string;
          total?: number;
          vendor_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "purchase_orders_entity_id_fkey";
            columns: ["entity_id"];
            isOneToOne: false;
            referencedRelation: "entities";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "purchase_orders_location_id_fkey";
            columns: ["location_id"];
            isOneToOne: false;
            referencedRelation: "locations";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "purchase_orders_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "purchase_orders_vendor_id_fkey";
            columns: ["vendor_id"];
            isOneToOne: false;
            referencedRelation: "vendors";
            referencedColumns: ["id"];
          },
        ];
      };
      rate_limits: {
        Row: {
          count: number;
          key: string;
          window_start: string;
        };
        ComputedFields: never;
        Insert: {
          count?: number;
          key: string;
          window_start: string;
        };
        Update: {
          count?: number;
          key?: string;
          window_start?: string;
        };
        Relationships: [];
      };
      recommendations: {
        Row: {
          action: Database["public"]["Enums"]["decision_action"];
          confidence: number;
          exception_id: string;
          hold_amount: number | null;
          id: string;
          pay_amount: number | null;
          reasons: NonNullable<Json>;
        };
        ComputedFields: never;
        Insert: {
          action: Database["public"]["Enums"]["decision_action"];
          confidence: number;
          exception_id: string;
          hold_amount?: number | null;
          id?: string;
          pay_amount?: number | null;
          reasons: NonNullable<Json>;
        };
        Update: {
          action?: Database["public"]["Enums"]["decision_action"];
          confidence?: number;
          exception_id?: string;
          hold_amount?: number | null;
          id?: string;
          pay_amount?: number | null;
          reasons?: NonNullable<Json>;
        };
        Relationships: [
          {
            foreignKeyName: "recommendations_exception_id_fkey";
            columns: ["exception_id"];
            isOneToOne: true;
            referencedRelation: "exceptions";
            referencedColumns: ["id"];
          },
        ];
      };
      tolerance_policies: {
        Row: {
          abs_amount: number;
          created_at: string;
          created_by: string | null;
          effective_from: string;
          id: string;
          org_id: string;
          pct: number;
        };
        ComputedFields: never;
        Insert: {
          abs_amount?: number;
          created_at?: string;
          created_by?: string | null;
          effective_from?: string;
          id?: string;
          org_id: string;
          pct?: number;
        };
        Update: {
          abs_amount?: number;
          created_at?: string;
          created_by?: string | null;
          effective_from?: string;
          id?: string;
          org_id?: string;
          pct?: number;
        };
        Relationships: [
          {
            foreignKeyName: "tolerance_policies_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      ui_events: {
        Row: {
          at: string;
          exception_id: string | null;
          id: number;
          kind: string;
          org_id: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          at?: string;
          exception_id?: string | null;
          id?: number;
          kind: string;
          org_id: string;
          user_id: string;
        };
        Update: {
          at?: string;
          exception_id?: string | null;
          id?: number;
          kind?: string;
          org_id?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "ui_events_exception_id_fkey";
            columns: ["exception_id"];
            isOneToOne: false;
            referencedRelation: "exceptions";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "ui_events_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
      vendor_aliases: {
        Row: {
          alias: string;
          vendor_id: string;
        };
        ComputedFields: never;
        Insert: {
          alias: string;
          vendor_id: string;
        };
        Update: {
          alias?: string;
          vendor_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "vendor_aliases_vendor_id_fkey";
            columns: ["vendor_id"];
            isOneToOne: false;
            referencedRelation: "vendors";
            referencedColumns: ["id"];
          },
        ];
      };
      vendors: {
        Row: {
          bank_fingerprint: string | null;
          bank_last4: string | null;
          category: string | null;
          contact_email: string | null;
          created_at: string;
          created_by: string | null;
          display_name: string;
          erp_vendor_ref: Json | null;
          id: string;
          legal_name: string | null;
          match_mode: Database["public"]["Enums"]["match_mode"];
          org_id: string;
          remit_address: Json | null;
          remit_address_changed_at: string | null;
          tax_id_hash: string | null;
          tax_id_last4: string | null;
          w9_bank_fingerprint: string | null;
          w9_on_file: boolean;
        };
        ComputedFields: never;
        Insert: {
          bank_fingerprint?: string | null;
          bank_last4?: string | null;
          category?: string | null;
          contact_email?: string | null;
          created_at?: string;
          created_by?: string | null;
          display_name: string;
          erp_vendor_ref?: Json | null;
          id?: string;
          legal_name?: string | null;
          match_mode?: Database["public"]["Enums"]["match_mode"];
          org_id: string;
          remit_address?: Json | null;
          remit_address_changed_at?: string | null;
          tax_id_hash?: string | null;
          tax_id_last4?: string | null;
          w9_bank_fingerprint?: string | null;
          w9_on_file?: boolean;
        };
        Update: {
          bank_fingerprint?: string | null;
          bank_last4?: string | null;
          category?: string | null;
          contact_email?: string | null;
          created_at?: string;
          created_by?: string | null;
          display_name?: string;
          erp_vendor_ref?: Json | null;
          id?: string;
          legal_name?: string | null;
          match_mode?: Database["public"]["Enums"]["match_mode"];
          org_id?: string;
          remit_address?: Json | null;
          remit_address_changed_at?: string | null;
          tax_id_hash?: string | null;
          tax_id_last4?: string | null;
          w9_bank_fingerprint?: string | null;
          w9_on_file?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: "vendors_org_id_fkey";
            columns: ["org_id"];
            isOneToOne: false;
            referencedRelation: "orgs";
            referencedColumns: ["id"];
          },
        ];
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      audit_row_digest: {
        Args: {
          p_action: string;
          p_actor_id: string;
          p_actor_type: Database["public"]["Enums"]["actor_type"];
          p_after: Json;
          p_at: string;
          p_before: Json;
          p_entity_id: string;
          p_entity_type: string;
          p_org: string;
          p_prev: string;
        };
        Returns: string;
      };
      audit_verify: { Args: { p_org: string }; Returns: number };
    };
    Enums: {
      actor_type: "system" | "user" | "core" | "agent" | "mcp";
      channel: "email" | "photo" | "portal" | "edi" | "upload";
      cost_kind: "llm" | "ocr" | "infra" | "human";
      decision_action:
        | "confirm_fields"
        | "short_pay"
        | "approve_as_is"
        | "dispute"
        | "link_po"
        | "approve_without_po"
        | "merge"
        | "reject_copy"
        | "not_duplicate"
        | "request_w9"
        | "release_hold"
        | "reject_invoice"
        | "retry_posting";
      erp_system: "quickbooks" | "netsuite" | "none";
      event_status:
        | "started"
        | "succeeded"
        | "failed"
        | "skipped"
        | "waiting"
        | "resumed";
      exception_status:
        | "open"
        | "awaiting_vendor"
        | "disputed"
        | "resolved"
        | "escalated";
      exception_type:
        | "extraction_review"
        | "price_variance"
        | "qty_mismatch"
        | "no_po"
        | "unmatched_line"
        | "duplicate"
        | "new_vendor_screen"
        | "posting_failed";
      field_source: "llm" | "ocr" | "edi" | "human" | "rule";
      invoice_status:
        | "received"
        | "extracted"
        | "in_review"
        | "enriched"
        | "screened"
        | "matched"
        | "awaiting_decision"
        | "approved"
        | "posting"
        | "posted"
        | "rejected"
        | "duplicate"
        | "failed";
      invoice_verdict:
        | "clean"
        | "price_variance"
        | "qty_mismatch"
        | "no_po"
        | "unmatched_line"
        | "mixed";
      line_verdict:
        | "matched"
        | "price_variance"
        | "qty_over_receipt"
        | "qty_over_order"
        | "unmatched_line"
        | "favorable";
      match_mode: "three_way" | "two_way";
      member_role:
        | "viewer"
        | "ap_clerk"
        | "ap_manager"
        | "controller"
        | "admin";
      stage:
        | "intake"
        | "extraction"
        | "review"
        | "enrichment"
        | "screening"
        | "match"
        | "approval"
        | "posting"
        | "notify"
        | "close";
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
};

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">;

type DefaultSchema = DatabaseWithoutInternals[Extract<
  keyof Database,
  "public"
>];

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R;
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R;
      }
      ? R
      : never
    : never;

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I;
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I;
      }
      ? I
      : never
    : never;

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U;
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U;
      }
      ? U
      : never
    : never;

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never;

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never;

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {
      actor_type: ["system", "user", "core", "agent", "mcp"],
      channel: ["email", "photo", "portal", "edi", "upload"],
      cost_kind: ["llm", "ocr", "infra", "human"],
      decision_action: [
        "confirm_fields",
        "short_pay",
        "approve_as_is",
        "dispute",
        "link_po",
        "approve_without_po",
        "merge",
        "reject_copy",
        "not_duplicate",
        "request_w9",
        "release_hold",
        "reject_invoice",
        "retry_posting",
      ],
      erp_system: ["quickbooks", "netsuite", "none"],
      event_status: [
        "started",
        "succeeded",
        "failed",
        "skipped",
        "waiting",
        "resumed",
      ],
      exception_status: [
        "open",
        "awaiting_vendor",
        "disputed",
        "resolved",
        "escalated",
      ],
      exception_type: [
        "extraction_review",
        "price_variance",
        "qty_mismatch",
        "no_po",
        "unmatched_line",
        "duplicate",
        "new_vendor_screen",
        "posting_failed",
      ],
      field_source: ["llm", "ocr", "edi", "human", "rule"],
      invoice_status: [
        "received",
        "extracted",
        "in_review",
        "enriched",
        "screened",
        "matched",
        "awaiting_decision",
        "approved",
        "posting",
        "posted",
        "rejected",
        "duplicate",
        "failed",
      ],
      invoice_verdict: [
        "clean",
        "price_variance",
        "qty_mismatch",
        "no_po",
        "unmatched_line",
        "mixed",
      ],
      line_verdict: [
        "matched",
        "price_variance",
        "qty_over_receipt",
        "qty_over_order",
        "unmatched_line",
        "favorable",
      ],
      match_mode: ["three_way", "two_way"],
      member_role: ["viewer", "ap_clerk", "ap_manager", "controller", "admin"],
      stage: [
        "intake",
        "extraction",
        "review",
        "enrichment",
        "screening",
        "match",
        "approval",
        "posting",
        "notify",
        "close",
      ],
    },
  },
} as const;
