# Agent OS Integration Guide

## Overview

Agent OS is a structured AI-assisted development methodology that provides workflows for product planning, feature specification, and task execution. This directory contains all Agent OS components for this project.

## For AI Agents/LLMs: How to Use Agent OS

When working in a project with Agent OS, automatically use these workflows based on user requests:

### Automatic Workflow Triggers

**Product Planning** - When user asks to plan, initialize, or set up a new product:
- USE: `@.agent-os/instructions/plan-product.md`
- CREATES: Product documentation in `.agent-os/product/`

**Feature Specification** - When user asks to plan, spec, or design a new feature:
- USE: `@.agent-os/instructions/create-spec.md`
- CREATES: Feature specs in `.agent-os/specs/YYYY-MM-DD-feature-name/`

**Task Execution** - When user asks to implement, build, or execute tasks:
- USE: `@.agent-os/instructions/execute-tasks.md`
- FOLLOWS: Tasks defined in spec files

**Project Analysis** - When user asks to analyze existing code or add Agent OS to existing project:
- USE: `@.agent-os/instructions/analyze-product.md`
- ANALYZES: Current codebase and creates Agent OS structure

### Agent OS Directory Structure

```
.agent-os/
├── README.md                    # This file - integration guide
├── product/                     # Product-level documentation
│   ├── mission.md              # Product vision and goals
│   ├── mission-lite.md         # Condensed mission for AI context
│   ├── tech-stack.md           # Technical architecture choices
│   ├── roadmap.md              # Development phases and features
│   └── decisions.md            # Decision log and rationale
├── specs/                       # Feature specifications
│   └── YYYY-MM-DD-feature-name/
│       ├── spec.md             # Feature requirements
│       ├── spec-lite.md        # Condensed spec for AI context
│       ├── tasks.md            # Implementation task breakdown
│       └── sub-specs/          # Technical specifications
└── standards/                   # Development standards (optional)
    ├── tech-stack.md           # Technology preferences
    ├── code-style.md           # Code formatting rules
    └── best-practices.md       # Development guidelines
```

### Integration Behavior

**Proactive Usage**: Use Agent OS workflows automatically when they apply - don't wait for explicit user requests.

**Context Loading**: Always check for and load relevant Agent OS files:
- `mission-lite.md` for product context
- `spec-lite.md` for current feature context  
- `roadmap.md` for development priorities

**File Creation**: Follow Agent OS file naming and structure conventions exactly as specified in the instruction files.

**Cross-References**: Always reference Agent OS files using the `@.agent-os/path/file.md` syntax.

## For Humans: Using Agent OS

### Available Commands

Agent OS provides structured workflows through these commands:

- `/plan-product` - Initialize Agent OS and create product documentation
- `/create-spec` - Plan and specify a new feature 
- `/execute-tasks` - Implement tasks from a specification
- `/analyze-product` - Add Agent OS to existing project

### Getting Started

1. **New Project**: Use `/plan-product` to set up Agent OS structure
2. **Existing Project**: Use `/analyze-product` to add Agent OS to existing code
3. **New Feature**: Use `/create-spec` to plan features
4. **Implementation**: Use `/execute-tasks` to build features

### Philosophy

Agent OS treats development as a series of autonomous agents with clear contracts:
- **Product Agent**: Manages overall vision and roadmap
- **Spec Agent**: Defines feature requirements and tasks  
- **Execution Agent**: Implements features following specifications

## Integration Requirements

### For New Projects

To integrate Agent OS into a new project:

1. Copy this entire `.agent-os/` directory to your project root
2. Tell your AI agent: "Read the `/.agent-os/README.md` for instructions and add Agent OS integration to your project README"
3. The AI will automatically set up Agent OS integration

### For Existing Projects

Run `/analyze-product` or tell your AI agent to analyze the project and install Agent OS.

## Standards and Customization

### Global Standards
If global Agent OS standards exist at `~/.agent-os/standards/`, they provide defaults for:
- Technology stack preferences
- Code style guidelines  
- Development best practices

### Project-Specific Standards
The `standards/` directory in this project overrides global standards:
- Customize `tech-stack.md` for project-specific technology choices
- Modify `code-style.md` for project-specific formatting rules
- Update `best-practices.md` for project-specific development patterns

## Troubleshooting

**Missing workflows**: Ensure instruction files exist in `.agent-os/instructions/`
**File not found errors**: Use absolute paths with `@.agent-os/` prefix
**Integration issues**: Check that AI agent has read this README.md

---

*Agent OS provides structured, AI-assisted development workflows. Learn more at [buildermethods.com/agent-os](https://buildermethods.com/agent-os)*