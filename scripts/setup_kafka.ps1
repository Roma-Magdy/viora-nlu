# Viora Kafka Initialization Script for Windows
Write-Host "Waiting for Kafka to stabilize (10 seconds)..." -ForegroundColor Cyan
Start-Sleep -s 10

# The 4 essential pathways for the Viora pipeline
$topics = @("user-commands", "vision-request", "vision-response", "final-action-ar")

foreach ($topic in $topics) {
    Write-Host "Creating Kafka topic: $topic" -ForegroundColor Yellow
    

    docker exec viora-kafka-1 /usr/bin/kafka-topics `
        --create `
        --bootstrap-server localhost:9092 `
        --replication-factor 1 `
        --partitions 1 `
        --topic $topic
}

Write-Host "All pathways are open. Viora is ready" -ForegroundColor Green