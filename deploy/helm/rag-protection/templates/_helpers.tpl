{{- define "rag-protection.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rag-protection.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "rag-protection.labels" -}}
helm.sh/chart: {{ include "rag-protection.name" . }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "rag-protection.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "rag-protection.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-protection.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "rag-protection.qdrantUrl" -}}
{{- if .Values.qdrant.enabled -}}
http://{{ include "rag-protection.fullname" . }}-qdrant:{{ .Values.qdrant.port }}
{{- else -}}
http://localhost:6333
{{- end -}}
{{- end }}

{{- define "rag-protection.validate" -}}
{{- $replicas := int .Values.replicaCount -}}
{{- if gt $replicas 1 -}}
{{- $backend := .Values.proxy.storeBackend | default "sqlite" | lower -}}
{{- if or (eq $backend "sqlite") (eq $backend "hybrid") -}}
{{- fail "replicaCount > 1 is the two-pod demo slice, not silent HA. Use proxy.storeBackend=vector (or pgvector) with shared Qdrant/Postgres. sqlite and hybrid keep a per-pod lexical DB. Overlay: values-ha-demo.yaml." -}}
{{- end -}}
{{- if and .Values.persistence.enabled (eq (.Values.persistence.accessMode | default "ReadWriteOnce") "ReadWriteOnce") -}}
{{- fail "replicaCount > 1 cannot mount a ReadWriteOnce PVC on every pod. Set persistence.enabled=false (emptyDir) and share Qdrant/pgvector. Overlay: values-ha-demo.yaml." -}}
{{- end -}}
{{- if .Values.proxy.audit.file -}}
{{- fail "replicaCount > 1 with proxy.audit.file set would split or corrupt JSONL. Leave audit.file empty (in-memory / webhook-only). Overlay: values-ha-demo.yaml." -}}
{{- end -}}
{{- end -}}
{{- end }}
