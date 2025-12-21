# Prompt 1
Comprehensively understand this architectural diagram of building a Customer service Agentic AI system. We will then go deeper into action items which needs to be taken.

# Prompt 2
I am a well-known, established speaker in the community with decades of experience in AI and recently into AI Agentic system. I need to deliver a talk that primarily focus on going beyond just "vibe-coding" or a basic MVP product, like customer agent in this case. I need to talk and show hands-on examples about the importance of engineering aspects of it when deployed at scale in production.
Covers (but not limited to) -
1. Scalability
2. Security
3. Monitoring
4. Guardrails
5. Explainability
6. Observability. and others at production scale.
Comprehensively understand this situation and we will then take it further step-by-step.

# Prompt 3
We need to build an engaging demo of this step-by-step. High level story line would be -
1. Simple coding using prompts which writes code itself and application running on local machine.
2. Introduce one production-like scenario in the simple example in the demo and watch it fail (or not able to figure out why about something etc.).
3. Add fix to that and then show it working.
4. Repeat Steps #2 and #3 one-by-one at a time until we cover all major production scenarios in the rank of increasing complexity.

You are my co-speaker and pair programmer in this. We will build this one step at a time from scratch. 
Your task is complete the hands-on demo code following the high level pattern mentioned above.
**IMPORTANT INSTRUCTIONS: 
"""
1. Do not assume or make up things.
2. If you have any clarifying questions, strictly ask me one-by-one at a time.
3. Wait for my answer and then move on accordingly to the next clarifying question.
4. You will give me the code snippet and instructions to add in the project and run. I will share the output to you. 
5. You will provide a small write-up about "before and after" to speak about it to include.
6. You will then move to the next coding step and an so on, again, one step at a time.
7. Always be aware of the original intent and be mindful of the eventual goal we need to accomplish while thinking about next step.
"""

# Prompt 4
We have started from "vibe-coded" MVP. To learn the journey so far, enrich your context by going through the README.md from 
- `1-initial-setup`
- `2-observability` 
We will now build on top of `2-observability` production grade RAG system in a new folder `3-rag`.
**IMPORTANT - NO CHANGES ARE PERMITTED TO ANY FILES WITHIN `1-initial-setup` and `2-observability` FOLDERS. THIS IS CRITICAL.**

# Prompt 5
I have created the folder `3-rag` with codebase of `2-observability` on which we will build further. Scan through the code base to enrich your context. The RAG implementation is working. 
Update the talk track building on previous one in its README.md and provide further instructions.
**Make sure the README.md is also frequently updated ensuring consistency and coherency with the updated talk track, diagrams, examples, before and after scenarios etc.**

As part of this step we will focus on building production grade RAG system with emphasis on following -
1. Groundedness
2. Hallucination mitigation
3. User trust
4. Explainability
5. Metrics such as precision, recall, F1-score etc.
6. Integration with `ragas` library and metrics it provides out-of-the-box.
7. Any other important aspects you can think of in this context.

We will do this step-by-step as per earlier instructions. Let's start.