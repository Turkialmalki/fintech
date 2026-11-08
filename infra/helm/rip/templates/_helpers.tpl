{{- define "rip.labels" -}}
app.kubernetes.io/part-of: rip
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}
