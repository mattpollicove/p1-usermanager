# GitHub Copilot: /create-agent Guide for p1-usermanager

*Created: April 27, 2026*

## What is `/create-agent`?

`/create-agent` helps you create **custom AI agents** - specialized assistants with specific roles, tools, and expertise tailored to your workflow. Think of them as expert team members you can delegate focused tasks to.

## How It Works

You describe what you need, and it creates a `.agent.md` file that defines:
- **Role & expertise** - What the agent specializes in
- **Available tools** - Which actions it can take (read-only, editing, execution, etc.)
- **Behavior rules** - What it should/shouldn't do
- **When to use it** - Trigger phrases for automatic delegation

## Perfect Use Cases for Your Project

Given your LDAP/database user manager with strict development rules, here are powerful examples:

### 1. Code Review Agent
Enforces your extensive checklist from DEVELOPMENT_RULES.md:

**Creation command:**
```
/create-agent a strict code reviewer that verifies:
- Qt widget-before-signal order
- blockSignals wrapping for bulk operations
- Timer shutdown guards in closeEvent
- Scalar string coercion for LDAP/DB fields
- PEP 8 compliance
Read-only access, returns checklist violations
```

**What it does**: Before committing changes, ask this agent to review your code. It catches the specific bugs you've documented in pastissues.md.

### 2. Performance Audit Agent
Specializes in your TPS logging system:

**Creation command:**
```
/create-agent analyze performance_stats.csv and identify bottlenecks
Expertise in bulk operations, database imports, LDAP sync
Suggests optimizations based on TPS patterns
Tools: read, search (no editing)
```

**What it does**: Hand it your performance_stats.csv data and get actionable insights about which operations need optimization.

### 3. LDAP Schema Agent
Handles all LDAP-specific work:

**Creation command:**
```
/create-agent LDAP schema specialist
Validates LDIF syntax, field mappings, attribute conversions
Ensures employeeNumber, postalCode stay as strings
Tools: read, search, edit (only ldap_utils.py and *.ldif files)
```

**What it does**: Safeguards against type coercion bugs when working with LDAP data transformations.

### 4. Documentation Sync Agent
Maintains your docs:

**Creation command:**
```
/create-agent keep help docs synchronized with code changes
Updates README, UI dialogs, APP_CHANGES_FOR_MIGRATION.md
Validates cross-platform consistency
Tools: read, search, edit (docs only)
```

**What it does**: Automatically enforces your rule to update help docs with every functional change.

### 5. Testing & Validation Agent
Knows your testing workflow:

**Creation command:**
```
/create-agent runs syntax checks and import tests
Executes: python -m py_compile on modified files
Runs import tests from workers, ui modules, api
Uses get_errors tool to verify compilation
Tools: execute, read, search
```

**What it does**: After any code changes, delegates to this agent to run your standard testing checklist before marking work complete.

## Real Workflow Example

Imagine you're adding a new bulk export feature:

1. **Main agent** (GitHub Copilot): Plans the implementation
2. **Delegation to Code Review Agent**: Validates against your pre-change checklist
3. **Delegation to Performance Agent**: Suggests optimal batch sizes based on historical TPS
4. **Delegation to Documentation Agent**: Updates all relevant help text
5. **Delegation to Testing Agent**: Runs py_compile and import tests

All automatic, all enforcing your specific standards.

## Agent Configuration Details

### Where Agents Live
- **Workspace-wide**: `.github/agents/*.agent.md` (shared with team)
- **Personal**: `~/Library/Application Support/Code/User/prompts/agents/` (just for you)

### Tool Aliases Available
- `execute` - Run shell commands
- `read` - Read file contents
- `edit` - Edit files
- `search` - Search files or text
- `agent` - Invoke other custom agents
- `web` - Fetch URLs and web search
- `todo` - Manage task lists

### Common Tool Combinations
- `[read, search]` - Read-only research agent
- `[read, edit, search]` - Can modify files but not run commands
- `[read, search, execute]` - Can analyze and test but not edit
- `[]` - Conversational only (planning, advice)

## How to Use Custom Agents

### Manual Invocation
In the GitHub Copilot chat, type:
```
@AgentName [your request]
```

### Automatic Delegation
The main agent will automatically delegate to your custom agents when:
- The task matches keywords in the agent's description
- The agent has the right tools for the job
- You're working in the agent's area of expertise

## Creating Your First Agent

Just use the `/create-agent` command in Copilot chat and describe what you need:

```
/create-agent [description of what the agent should do and what tools it needs]
```

Examples to try:
- "Create the code review agent"
- "Create a testing agent that knows our py_compile workflow"
- "Create an agent that only handles UI/Qt work"

---

## Benefits for p1-usermanager Development

1. **Consistency**: Agents enforce your documented rules automatically
2. **Speed**: Delegate specialized tasks without re-explaining context
3. **Quality**: Catch bugs from pastissues.md before they happen again
4. **Focus**: Main agent handles coordination, specialists handle execution
5. **Documentation**: Agent definitions serve as executable documentation of your standards

## Next Steps

Consider creating these agents first:
1. **Code Review Agent** - Catches Qt/LDAP/import bugs from your checklist
2. **Testing Agent** - Automates your py_compile and import test workflow
3. **Performance Agent** - Analyzes TPS data and suggests optimizations

These three would cover most of your development workflow and enforce the standards you've documented in DEVELOPMENT_RULES.md and pastissues.md.
