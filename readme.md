# Odoo 19 AI Accounting & Auditing Suite

A comprehensive Odoo 19 repository demonstrating custom module development, advanced ORM techniques, accounting workflow automation, security auditing and modern AI integrations.

This repository contains two distinct custom modules designed to automate, secure, and extend accounting workflows inside Odoo.

---

## Modules

* [Moroccan AI Expense Categorizer](#module-1-moroccan-ai-expense-categorizer-moroccan_ai_expense)
* [AI Invoice Auditor & Security Logger](#module-2-ai-invoice-auditor--security-logger-ai_invoice_auditor)

---

# Module 1: Moroccan AI Expense Categorizer

**Technical module:** `moroccan_ai_expense`

An accounting staging area that ingests raw expense descriptions and uses a two-step LLM pipeline to automatically classify them under the Moroccan Chart of Accounts — the **Plan Comptable Général Marocain (PCGM)**.

Once the expense has been reviewed and approved, the module automates the generation of official, balanced double-entry journal entries in Odoo's accounting ledger.

---

## The Business Problem

Manual expense entry is slow and prone to human error.

An accountant may receive a description such as:

> "Achat carburant Total"

and need to manually map it to the correct accounting account.

While LLMs are good at semantic matching, they can also hallucinate accounting codes that do not exist in the company's actual chart of accounts.

Connecting an LLM directly to a live accounting ledger would therefore be unsafe.

---

## Solution & Architecture

### 1. The Staging Table Pattern

AI should not write directly to an official accounting ledger.

The module introduces a custom staging model:

```text
moroccan.raw.expenses
```

The workflow is:

```text
Raw Expense
    │
    ▼
Staging Area
    │
    ▼
AI Classification
    │
    ▼
Accountant Review
    │
    ▼
Approval
    │
    ▼
Official Journal Entry
(account.move)
```

Users enter raw expense information into the staging area:

* Expense description
* Amount
* Date
* Proposed accounting account

The AI then proposes an account classification.

A human accountant reviews the result before the expense is posted to the official ledger.

Only after approval does the system generate the official journal entry.

This creates a separation between:

> **AI-assisted suggestions**

and

> **Official financial records**

---

### 2. Two-Step LLM Pipeline

The classification pipeline is designed to prevent the AI from inventing accounting codes.

The integration uses:

* LiteLLM
* Pydantic
* Gemini or other configurable LLM providers
* Odoo's live accounting database

#### Step 1: Semantic Categorization

The first LLM analyzes the raw expense description and determines the most likely principal accounting category.

For example:

```text
"Achat carburant Total"
        │
        ▼
Principal Category: 6142
```

The output is validated using a Pydantic schema.

---

#### Step 2: Database Grounding

The Odoo backend uses the predicted principal category to query the live database.

It retrieves the active detailed accounts that actually exist in the company's chart of accounts.

For example:

```text
Principal Category: 6142
        │
        ▼
PostgreSQL / Odoo ORM
        │
        ▼
Available Accounts:
├── 614201
├── 614202
├── 614203
└── 614204
```

Only accounts that actually exist in the database are passed to the second LLM.

---

#### Step 3: Strict Account Selection

The second LLM receives the list of valid accounts and is instructed to select only one of them.

The model cannot freely invent an accounting code.

The final response is validated with Pydantic before the Python backend uses it.

```text
Raw Description
      │
      ▼
LLM #1
Semantic Classification
      │
      ▼
Principal Account Category
      │
      ▼
Odoo Database Query
      │
      ▼
Valid Existing Accounts
      │
      ▼
LLM #2
Strict Selection
      │
      ▼
Pydantic Validation
      │
      ▼
Proposed Accounting Account
```

This architecture combines:

* LLM semantic reasoning
* Database grounding
* Structured output validation
* Human approval

---

## 3. Two-Way Data Synchronization

The staging record and the official journal entry are kept synchronized.

### Manual Push: Expense → Ledger

If a user modifies the raw expense after it has been posted, a computed field using:

```python
@api.depends
```

detects whether the staging record and the linked journal entry are out of sync.

If a difference is detected, an **Update** action becomes available.

To avoid partial inconsistencies in accounting lines, the module uses a controlled delete-and-recreate approach for draft journal entries.

---

### Automatic Reverse Synchronization: Ledger → Expense

An accountant may also bypass the staging area and modify the official journal entry directly.

The module inherits the core:

```text
account.move
```

model and overrides:

```python
write()
```

When relevant fields are changed directly on the journal entry, the changes are propagated back to the linked staging record.

This creates two-way synchronization:

```text
┌─────────────────────────────┐
│  Moroccan Expense Staging   │
└──────────────┬──────────────┘
               │
               │ Manual Update
               ▼
┌─────────────────────────────┐
│      Official Journal Entry │
│         account.move        │
└──────────────┬──────────────┘
               │
               │ Direct Accountant Edit
               ▼
        Automatic Reverse Sync
```

---

# Odoo Framework Features Demonstrated

## ORM & Database Operations

Extensive use of Odoo ORM operations, including:

* `search()`
* `create()`
* `write()`
* `unlink()`
* Recordset filtering with `filtered()`

---

## Relational Data Structures

Implementation of:

* `Many2one`
* `One2many`

including Odoo's relational command syntax for creating related accounting lines:

```python
(0, 0, {values})
```

This is used to generate balanced debit and credit journal entry lines.

---

## Security & Access Control

### Model Access Control Lists

Configured:

```text
ir.model.access.csv
```

to define model-level permissions.

### Record Rules

Configured:

```text
ir.rule
```

to enforce row-level security.

For example, standard employees can be restricted to viewing expenses they created.

---

## Automated Background Jobs

A scheduled Odoo Cron job:

```text
ir.cron
```

runs nightly and automatically removes abandoned draft expenses older than 30 days.

---

## Automated Testing

The module includes unit tests using:

```python
TransactionCase
```

to verify accounting generation logic in an isolated Odoo transaction environment.

The test environment automatically rolls back changes after execution, preventing test data from polluting the database.

---

## UI/UX Customization

The modules include:

* Custom XML form views
* List views
* Status bars
* Notebook tabs
* Cross-model navigation
* Dynamic actions and workflow controls

---

# Module 2: AI Invoice Auditor & Security Logger

**Technical module:** `ai_invoice_auditor`

An Odoo 19 module designed to intercept invoice confirmation attempts, perform security audits, and persistently log blocked actions.

---

## The Business Problem

When an ERP system blocks an action by raising a validation error, the database transaction is normally rolled back.

For example:

```text
User attempts to confirm invoice
            │
            ▼
Security validation fails
            │
            ▼
ValidationError raised
            │
            ▼
Transaction rolled back
            │
            ▼
Audit log is also deleted
```

This creates a problem:

> A blocked security attempt may leave no permanent record.

---

## Solution: Independent Database Cursor

The module uses a separate database cursor to persist security logs before the main transaction is aborted.

### How It Works

When a suspicious or invalid invoice confirmation is blocked:

1. The main transaction detects the violation.
2. A secondary database cursor is opened using:

```python
self.env.registry.cursor()
```

3. The security audit record is written through the independent cursor.
4. The audit log is committed.
5. The original operation raises a validation error.
6. The main transaction is rolled back.
7. The security log remains permanently stored.

Conceptually:

```text
┌─────────────────────────────┐
│      Main Transaction       │
│                             │
│  Invoice Confirmation       │
│           │                 │
│           ▼                 │
│    Security Violation      │
│           │                 │
│           ▼                 │
│    ValidationError         │
│           │                 │
│           ▼                 │
│       ROLLBACK             │
└─────────────────────────────┘

              ▲
              │
              │ Independent Cursor
              │
              ▼

┌─────────────────────────────┐
│      Audit Log Transaction  │
│                             │
│  Save Security Event        │
│           │                 │
│           ▼                 │
│          COMMIT             │
│                             │
│  Log survives rollback      │
└─────────────────────────────┘
```

This ensures that blocked security attempts remain auditable even when the original business transaction fails.

---

# REST API

The module exposes audit data through an Odoo HTTP controller.

Example endpoint:

```text
/api/audits
```

The controller uses:

* `http.Controller`
* `@http.route`
* JSON responses
* Odoo's native authenticated route configuration

The endpoint uses:

```python
auth='user'
```

to require an authenticated Odoo user.

This allows external compliance or monitoring systems to consume structured audit information.

---

# QWeb PDF Reporting

The module provides printable audit reports.

The report system:

* Uses QWeb templates
* Uses HTML/CSS
* Uses Bootstrap 5 styling
* Is connected to the Audit Log model
* Generates PDF summaries for compliance and security review

The system converts relational audit records into a structured, printable report.

---

# Technology Stack

| Category              | Technology                                               |
| --------------------- | -------------------------------------------------------- |
| ERP Framework         | Odoo 19                                                  |
| Programming Language  | Python 3.12                                              |
| Database              | PostgreSQL 15                                            |
| AI Integration        | LiteLLM                                                  |
| Structured Validation | Pydantic                                                 |
| LLM Provider          | Google Gemini                                            |
| Alternative Providers | OpenAI, Anthropic, and other LiteLLM-supported providers |
| Containerization      | Docker / Docker Compose                                  |
| Reporting             | QWeb / Bootstrap 5                                       |
| Testing               | Odoo TransactionCase                                     |

---

# Installation

## 1. Clone the Repository

Clone the repository into your Odoo custom addons directory.

```bash
git clone <repository-url>
```

---

## 2. Install Python Dependencies

Inside the Odoo Python environment:

```bash
pip install litellm pydantic
```

---

## 3. Configure the LLM API Key

Set the required API key as an environment variable.

For example:

```bash
GEMINI_API_KEY=your_api_key_here
```

---

## 4. Install the Odoo Modules

1. Start the Odoo environment.
2. Enable Developer Mode.
3. Update the Apps List.
4. Install:

```text
moroccan_ai_expense
ai_invoice_auditor
```

---

# Engineering Principles Demonstrated

This repository focuses on more than simply adding AI features to Odoo.

The project demonstrates several engineering principles:

### AI Should Not Directly Control Critical Systems

The AI proposes a result.

The application validates it.

A human approves it.

Only then does the system modify official accounting data.

---

### External Data Should Be Grounded in Authoritative Sources

The LLM does not invent accounting accounts.

The application retrieves valid accounts from the actual Odoo database and constrains the model to those choices.

---

### Failed Transactions Can Still Require Persistent Audit Trails

A transaction rollback should not necessarily erase evidence of a blocked security event.

The independent cursor pattern allows the audit event to survive the failed business transaction.

---

### ERP Development Requires Both Technical and Business Understanding

The project combines:

* Accounting workflows
* Moroccan accounting structures
* Odoo ORM
* Database design
* Security
* AI integration
* API development
* Reporting
* Testing

This repository represents a transition from general Python/Django development into Odoo and ERP application engineering.

