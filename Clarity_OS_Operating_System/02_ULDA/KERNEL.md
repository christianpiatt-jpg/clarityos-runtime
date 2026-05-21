# ULDA Kernel Specification 
The ULDA kernel is the minimal loop that must remain intact for the system to behave coherently. 
It is designed to be simple enough to remember under stress and rich enough to diagnose complex situations. 
 
## Purpose 
- Provide a stable loop for sense-making and action. 
- Make decisions inspectable and explainable after the fact. 
- Allow operators to notice drift, overload, or manipulation. 
 
## Phases of the ULDA loop 
1. Observe: Gather signals from the environment and from inside the system. 
2. Locate: Place those signals in a frame, map, or geometry. 
3. Diagnose: Identify what pattern is present and what is actually happening. 
4. Adjust: Choose and apply a change, command, or boundary. 
5. Review: Check what changed and whether the loop stayed intact. 
 
## Invariants 
- The loop must be able to complete, even under pressure. 
- Each phase must be nameable and separable from the others. 
- The operator must be able to say where they are in the loop. 
- The loop must be restartable without losing integrity. 
 
## Inputs and outputs 
- Inputs: signals, events, constraints, goals, and prior state. 
- Outputs: decisions, commands, boundaries, and updated maps. 
 
## Failure modes 
- Stuck in Observe: collecting signals without moving to action. 
- Skipping Diagnose: acting on first impression without checking pattern. 
- No Review: never checking whether the loop is working. 
- External hijack: someone else forcing the loop to run on their terms. 
