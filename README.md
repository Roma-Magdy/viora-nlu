# Viora NLU – Test Application & Kafka Architecture

This repository contains the **Viora NLU test application** and the Kafka-based architecture used to support communication between the system's components.

It provides a testing environment for the Natural Language Understanding (NLU) engine and demonstrates how the different services communicate through Apache Kafka.

## 1. Test Application

This repository includes a test application for interacting with and testing the NLU engine.

It allows developers to check how user inputs are processed and how the engine returns structured results.

## 2. Kafka Architecture

The project uses **Apache Kafka** to support asynchronous communication between services.

The Kafka architecture demonstrates how messages are exchanged between system components, helping connect the NLU engine with other backend services.

## 3. NLU Engine

The NLU Engine: is available here: https://github.com/Roma-Magdy/Viora-Distributed-NLU-Vision-System-for-the-Blind

The NLU engine serves as the AI core of Viora. It processes user speech or text and converts it into structured information that can be used by the system.

Its main responsibilities include:
- **Intent Classification:** Identifying the user's intended action.
- **Entity Extraction:** Extracting relevant information from user input.
- **Input Processing:** Preparing speech or text inputs for the system's backend.
