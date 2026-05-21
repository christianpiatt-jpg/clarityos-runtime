# Executive Layer Overview 
The Executive Layer is the OS's action engine. 
It determines what to do, when to do it, and how to maintain coherence across actions. 
 
## Core responsibilities 
- Convert ULDA outputs into decisions. 
- Issue commands that are clear, bounded, and actionable. 
- Maintain sequencing: what comes first, next, and last. 
- Track commitments and ensure follow-through. 
 
## Executive constraints 
- No command may violate geometry constraints. 
- No decision may skip ULDA Diagnose. 
- No action may collapse the operator's frame. 
 
## Executive failure modes 
- Over-commanding: issuing too many commands too fast. 
- Under-commanding: avoiding decisions and letting drift take over. 
- Mis-sequencing: doing the right things in the wrong order. 
- Frame collapse: acting from panic, not clarity. 
