FROM mcr.microsoft.com/dotnet/runtime:6.0

RUN apt-get update && apt-get install time -y

# Needs for readOnlyRootFilesystem: true
ENV COMPlus_EnableDiagnostics=0