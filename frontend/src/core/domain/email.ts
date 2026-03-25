/**
 * Tipos de domínio alinhados ao backend (classificação Produtivo | Improdutivo).
 * UI e infraestrutura dependem destes contratos, não o contrário.
 */

export type ProductivityCategory = "Produtivo" | "Improdutivo";

export type EmailProcessingStatus =
  | "pending"
  | "classified"
  | "sent"
  | "skipped"
  | "failed";
