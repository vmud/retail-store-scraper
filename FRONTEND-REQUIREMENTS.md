# Store Locator Scraper — Web Interface Requirements

> **Design Tool**: Subframe (React + Tailwind CSS)
> **Version**: 1.0
> **Last Updated**: January 2025

---

## Executive Summary

### What We're Building

A web interface for an existing CLI-based retail store locator scraping system. The backend already supports scraping store location data from 7 major retailers (Verizon, AT&T, T-Mobile, Target, Walmart, Best Buy, Telus) with features like concurrent execution, proxy rotation, checkpointing, and change detection.

The web UI will make this tool accessible to non-technical team members by providing:
1. **Job management** — Start, stop, and configure scraping jobs without CLI knowledge
2. **Real-time monitoring** — Watch job progress, view live logs, and track errors
3. **Data access** — Browse, search, filter, and download scraped store data
4. **Change tracking** — Compare scrape results over time to identify new/closed stores

### Target Users

| User Type | Goals | Frequency |
|-----------|-------|-----------|
| **Data Analyst** | Download store lists, browse data, compare changes | Daily |
| **Operations Lead** | Monitor job status, troubleshoot failures | Daily |
| **Admin** | Configure scrapers, manage users, set retention | Weekly |

All users are internal team members. No external/public access required.

### Key User Flows

**Flow 1: Run a Scrape**
`Login → Dashboard → Click "New Job" → Select retailers → Configure options → Start → Monitor progress → Download results`

**Flow 2: Get Store Data**
`Login → Data → Search/filter stores → View details or Download`

**Flow 3: Check What Changed**
`Login → Data → Changes tab → Select retailer & date range → Review new/closed/updated stores`

---

## Design Guidelines

### Visual Direction: Utilitarian & Information-Dense

This is a **power-user tool** for an internal team that uses it daily. Optimize for **information density** and **task efficiency** over aesthetics.

| Do | Don't |
|----|-------|
| Pack relevant data into views | Add excessive whitespace or padding |
| Show status/metrics at a glance | Hide information behind extra clicks |
| Use tables for data-heavy views | Use cards when tables are more efficient |
| Expose all options (via progressive disclosure) | Oversimplify to the point of limiting power users |
| Use clear, functional labels | Use clever or ambiguous copy |

### Layout Principles

- **Persistent sidebar navigation** — Users jump between Jobs, Data, and Downloads frequently
- **Tables as primary data display** — Most views are tabular; optimize table UX
- **Drawers for detail views** — Don't navigate away; slide out job details or store info
- **Dialogs for actions** — New Job, Invite User, Confirmations stay in modal context

### Information Hierarchy

1. **Primary**: Active job status, key metrics, action buttons
2. **Secondary**: Historical data, configuration options
3. **Tertiary**: Metadata, timestamps, technical details

### Color Usage

| Color | Usage |
|-------|-------|
| **Brand primary** | Primary actions, active navigation |
| **Green (success)** | Completed jobs, successful states |
| **Yellow (warning)** | Retrying, rate-limited, needs attention |
| **Red (error)** | Failed jobs, errors, destructive actions |
| **Gray (neutral)** | Pending states, disabled items, secondary text |

Use `Badge` component consistently for status indication across all views.

### Typography & Density

- Use default Subframe typography scale
- Favor **smaller text sizes** where appropriate for density
- Tables: compact row heights, no excessive padding
- Monospace font for: log output, store IDs, technical values

### Interaction Patterns

| Pattern | When to Use |
|---------|-------------|
| **Click row → Drawer** | Job list → Job detail, Store list → Store detail |
| **Hover → Tooltip** | Truncated text, disabled buttons, icon-only actions |
| **Dropdown menu** | Multiple actions per row (View, Download, Delete) |
| **Progressive disclosure** | Advanced job options, filters |
| **Inline editing** | User role changes, toggle settings |

### Loading & Empty States

Every data view needs:
- **Loading state**: Use `SkeletonText` for tables, `Loader` for actions
- **Empty state**: Helpful message + primary action (e.g., "No jobs yet. Start your first scrape.")
- **Error state**: `Alert` with retry action

### Real-Time Feedback

Jobs are long-running (minutes to hours). Users need confidence the system is working:
- **Progress bars** with percentage and counts
- **Live log streaming** (WebSocket)
- **Timestamps** showing last update
- **Toast notifications** for state changes

---

## Design Constraints

| Constraint | Implication |
|------------|-------------|
| Light mode only | No dark theme variants needed |
| Internal users only | No public marketing concerns; optimize for function |
| Small team (< 20 users) | No complex permission hierarchies |
| Desktop-primary | Mobile responsiveness is nice-to-have, not required |
| React + Tailwind | All Subframe components export as React/Tailwind |

---

## Overview

Web interface for the retail store locator scraping system. Enables non-technical users to initiate scraping jobs, monitor progress in real-time, and download/browse store data.

### Design Principles (Summary)
- **Utilitarian & information-dense** — Prioritize data visibility over whitespace
- **Light mode only** — No dark theme required
- **Power-user focused** — Expose full functionality, use progressive disclosure for complexity

---

## Available Subframe Components

The following components are already synced from Subframe and available for use:

### Layout
- `DefaultPageLayout` — Sidebar navigation + main content area
- `DialogLayout` — Modal dialogs
- `DrawerLayout` — Slide-out panels

### Navigation & Structure
- `SidebarWithSections` — Collapsible sidebar with nav items and sections
- `Tabs` — Tab navigation within pages
- `Breadcrumbs` — Page hierarchy navigation
- `Stepper` / `VerticalStepper` — Multi-step flows

### Data Display
- `Table` — Data tables with HeaderRow, Row, Cell, HeaderCell
- `Badge` — Status indicators
- `Progress` — Progress bars
- `LineChart` / `BarChart` / `AreaChart` / `PieChart` — Data visualization
- `Alert` — Informational/warning/error messages
- `Loader` — Loading states
- `SkeletonText` / `SkeletonCircle` — Loading placeholders

### Forms & Input
- `TextField` — Text input
- `TextArea` — Multi-line text input
- `Select` — Dropdown selection
- `Checkbox` / `CheckboxGroup` / `CheckboxCard` — Multi-select options
- `RadioGroup` / `RadioCardGroup` — Single-select options
- `Switch` — Toggle on/off
- `Slider` — Range input
- `Button` / `IconButton` / `LinkButton` — Actions

### Feedback & Overlays
- `Toast` — Transient notifications
- `Dialog` / `FullscreenDialog` — Modal dialogs
- `Drawer` — Slide-out panels
- `Tooltip` — Hover hints
- `DropdownMenu` / `ContextMenu` — Action menus

### Other
- `Avatar` — User avatars
- `Accordion` — Collapsible sections
- `TreeView` — Hierarchical data
- `CopyToClipboardButton` — Copy actions
- `IconWithBackground` — Icon containers
- `ToggleGroup` — Segmented controls
- `Calendar` — Date picker

---

## User Roles & Permissions

| Capability | Admin | User |
|------------|:-----:|:----:|
| Start/stop scraping jobs | ✓ | ✓ |
| View job status & progress | ✓ | ✓ |
| Download store data | ✓ | ✓ |
| Configure scrapers (proxies, concurrency) | ✓ | ✗ |
| Add/remove retailers | ✓ | ✗ |
| Manage users | ✓ | ✗ |
| Configure retention settings | ✓ | ✗ |

---

## Information Architecture

```
├── Authentication (no sidebar)
│   ├── Login (magic link request)
│   └── Verify (magic link callback)
│
├── Main App (DefaultPageLayout with sidebar)
│   ├── Dashboard (home)
│   ├── Jobs
│   │   ├── Active Jobs
│   │   ├── Job History
│   │   └── Job Detail (drawer or page)
│   ├── Data
│   │   ├── Browse Stores
│   │   ├── Map View
│   │   └── Change History
│   ├── Downloads
│   └── Settings (admin only)
│       ├── Scraper Configuration
│       ├── Retailers
│       ├── Users
│       └── Retention Policy
```

---

## Page Specifications

### Page 1: Login

**Route**: `/login`
**Layout**: Centered card (no sidebar)
**Access**: Public

#### Purpose
Request magic link for passwordless authentication.

#### Components
```
┌─────────────────────────────────────────────┐
│                                             │
│              [Logo/Brand]                   │
│                                             │
│     ┌─────────────────────────────────┐     │
│     │  Store Locator Scraper          │     │
│     │                                 │     │
│     │  Email address                  │     │
│     │  ┌─────────────────────────┐    │     │
│     │  │ TextField               │    │     │
│     │  └─────────────────────────┘    │     │
│     │                                 │     │
│     │  ┌─────────────────────────┐    │     │
│     │  │ Button: Send Magic Link │    │     │
│     │  └─────────────────────────┘    │     │
│     │                                 │     │
│     └─────────────────────────────────┘     │
│                                             │
└─────────────────────────────────────────────┘
```

#### States
- **Default**: Email input empty
- **Loading**: Button shows `Loader`, disabled
- **Success**: Show `Alert` (success) — "Check your email for a login link"
- **Error**: Show `Alert` (error) — Invalid email or rate limited

#### Subframe Components
- `TextField` (email input, type="email", required)
- `Button` (variant="brand-primary", loading state)
- `Alert` (success/error variants)

---

### Page 2: Dashboard

**Route**: `/` or `/dashboard`
**Layout**: `DefaultPageLayout`
**Access**: Authenticated

#### Purpose
At-a-glance overview of system status, active jobs, and recent activity.

#### Wireframe
```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR          │  MAIN CONTENT                                     │
│                  │                                                    │
│ [Logo]           │  Dashboard                          [+ New Job]   │
│                  │                                                    │
│ ○ Dashboard      │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│ ○ Jobs           │  │ Active   │ │ Completed│ │ Failed   │           │
│ ○ Data           │  │ Jobs: 2  │ │ Today: 5 │ │ Today: 0 │           │
│ ○ Downloads      │  └──────────┘ └──────────┘ └──────────┘           │
│                  │                                                    │
│ ─────────────    │  Active Jobs                                       │
│ ADMIN            │  ┌────────────────────────────────────────────┐   │
│ ○ Settings       │  │ Table                                      │   │
│                  │  │ Retailer | Status | Progress | Started     │   │
│ ─────────────    │  │ Verizon  | Running| ████░░ 67% | 10m ago  │   │
│ [Avatar] User    │  │ Target   | Running| ██░░░░ 34% | 5m ago   │   │
│                  │  └────────────────────────────────────────────┘   │
│                  │                                                    │
│                  │  Recent Activity                                   │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │ • AT&T completed — 2,847 stores (2h ago)   │   │
│                  │  │ • Walmart completed — 4,742 stores (5h ago)│   │
│                  │  └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

#### Components & Data

**Stats Cards** (top row)
- 3x cards showing: Active Jobs, Completed Today, Failed Today
- Use `IconWithBackground` + text, or custom card component
- Clicking navigates to filtered Jobs view

**Active Jobs Table**
- `Table` component
- Columns: Retailer (with logo), Status (`Badge`), Progress (`Progress` bar + %), Started (relative time), Actions (`IconButton` for stop/view)
- Clickable rows → open Job Detail drawer
- Empty state: "No active jobs" with `Button` to start new job

**Recent Activity**
- Simple list or `Table` without header
- Shows last 5-10 completed/failed jobs
- Each row: retailer icon, outcome, store count, timestamp

#### Subframe Components
- `DefaultPageLayout`
- `Table`, `Table.Row`, `Table.Cell`, `Table.HeaderRow`, `Table.HeaderCell`
- `Badge` (variants: success, warning, error, neutral)
- `Progress`
- `Button` (+ New Job)
- `IconButton` (row actions)
- `Drawer` (job detail panel)

---

### Page 3: New Job (Dialog)

**Route**: Modal overlay (no route change) or `/jobs/new`
**Layout**: `FullscreenDialog` or `Dialog`
**Access**: Authenticated

#### Purpose
Configure and start a new scraping job with progressive disclosure of options.

#### Wireframe
```
┌─────────────────────────────────────────────────────────────────┐
│  New Scraping Job                                          [X]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Select Retailers                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☑ Verizon    ☑ AT&T       ☑ T-Mobile                   │   │
│  │ ☑ Target     ☐ Walmart    ☐ Best Buy    ☐ Telus        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Output Format                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Select: [JSON ▼]  (JSON, CSV, Excel, GeoJSON, All)      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ▶ Advanced Options                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Concurrency     [Slider: 1-10, default 5]               │   │
│  │ Use Proxy       [Switch: On/Off]                        │   │
│  │ Resume from     [Select: Fresh / Last Checkpoint]       │   │
│  │ Geographic Filter [TextField: State codes, optional]    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────────────────────┐      │
│  │ Cancel          │  │ Start Job (3 retailers)         │      │
│  └─────────────────┘  └─────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Sections

**1. Retailer Selection** (required)
- `CheckboxCard` or `CheckboxGroup` for each supported retailer
- Show retailer logo + name
- Indicate if retailer already has a running job (disabled + tooltip)
- At least one must be selected

**2. Output Format** (required)
- `Select` dropdown
- Options: JSON, CSV, Excel, GeoJSON, All Formats
- Default: JSON

**3. Advanced Options** (collapsed by default)
- `Accordion` to show/hide
- **Concurrency**: `Slider` (1-10, default: 5)
- **Use Proxy**: `Switch` (default: on for production)
- **Resume Behavior**: `RadioGroup` — "Start Fresh" / "Resume from Checkpoint"
- **Geographic Filter**: `TextField` — comma-separated state codes (optional)
- **Change Detection**: `Switch` — Compare with previous run (default: off)

#### Validation
- At least one retailer selected
- Cannot start job for retailer with active job (show `Tooltip` explaining why disabled)

#### Subframe Components
- `Dialog` or `FullscreenDialog`
- `CheckboxCard` (retailer selection)
- `Select` (output format)
- `Accordion` (advanced options)
- `Slider` (concurrency)
- `Switch` (proxy, change detection)
- `RadioGroup` (resume behavior)
- `TextField` (geographic filter)
- `Button` (cancel: neutral-secondary, start: brand-primary)
- `Tooltip` (disabled states)

---

### Page 4: Job Detail (Drawer)

**Route**: Drawer overlay from Jobs list, or `/jobs/:id`
**Layout**: `DrawerLayout` (slide from right)
**Access**: Authenticated

#### Purpose
Real-time monitoring of a specific job with live logs, progress, and error visibility.

#### Wireframe
```
┌────────────────────────────────────────────────────────┐
│  Verizon Scraping Job                             [X]  │
│  Started: Jan 28, 2025 at 2:34 PM                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Status: Running                         [Stop Job]    │
│                                                        │
│  Progress                                              │
│  ┌──────────────────────────────────────────────────┐ │
│  │ ████████████████████░░░░░░░░░░  67%              │ │
│  │ 1,847 / 2,756 stores                             │ │
│  │ ETA: ~12 minutes                                 │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  [Tabs: Logs | Errors | Config ]                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Logs (live)                          [Auto-scroll]│ │
│  │ ──────────────────────────────────────────────── │ │
│  │ 14:45:23 Scraping store #1847 (San Jose, CA)     │ │
│  │ 14:45:22 Scraping store #1846 (Fremont, CA)      │ │
│  │ 14:45:21 Scraping store #1845 (Newark, CA)       │ │
│  │ 14:45:20 Checkpoint saved: page 67               │ │
│  │ ...                                              │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Errors (3)                                            │
│  ┌──────────────────────────────────────────────────┐ │
│  │ ⚠ Rate limited at store #1203 (retrying)        │ │
│  │ ⚠ Timeout at store #987 (retried successfully)  │ │
│  │ ✗ Failed store #456 (skipped)                   │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

#### Sections

**Header**
- Retailer name + logo
- Start timestamp
- Status `Badge` (Running, Completed, Failed, Stopped)
- Stop button (if running) — `Button` variant="destructive-secondary"

**Progress Panel**
- `Progress` bar with percentage
- Stores scraped / total (if known)
- Estimated time remaining
- Current checkpoint info (nice-to-have)

**Tabbed Content**
- `Tabs` component with 3 tabs:

**Tab 1: Logs**
- Monospace text area showing live log stream (WebSocket)
- Auto-scroll toggle (`Switch`)
- Most recent at top or bottom (configurable)
- Use `TextArea` styled as terminal, or custom log viewer

**Tab 2: Errors**
- `Table` or list of errors/warnings
- Columns: Timestamp, Type (`Badge`), Message, Action taken
- Filter by severity

**Tab 3: Config**
- Read-only display of job configuration
- Retailer, output format, concurrency, proxy status, etc.

#### Real-time Updates
- WebSocket connection for:
  - Progress updates (stores scraped, percentage)
  - Log streaming
  - Error events
  - Job completion/failure

#### Subframe Components
- `Drawer`
- `Badge` (status)
- `Progress`
- `Tabs`
- `Button` (stop job)
- `Switch` (auto-scroll)
- `Table` (errors)
- `Alert` (job completed/failed notification)

---

### Page 5: Jobs List

**Route**: `/jobs`
**Layout**: `DefaultPageLayout`
**Access**: Authenticated

#### Purpose
View all jobs (active and historical) with filtering and search.

#### Wireframe
```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR          │  MAIN CONTENT                                     │
│                  │                                                    │
│                  │  Jobs                                [+ New Job]   │
│                  │                                                    │
│                  │  [Tabs: Active | History | All ]                   │
│                  │                                                    │
│                  │  Filters: [Retailer ▼] [Status ▼] [Date Range]    │
│                  │                                                    │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │ Table                                      │   │
│                  │  │ Retailer | Status | Stores | Duration |... │   │
│                  │  │ ─────────────────────────────────────────  │   │
│                  │  │ Verizon  | ● Running | 1.8k/2.7k | 45m    │   │
│                  │  │ AT&T     | ✓ Done    | 2,847     | 2h 15m │   │
│                  │  │ Target   | ✗ Failed  | 1,203     | 30m    │   │
│                  │  │ ...                                        │   │
│                  │  └────────────────────────────────────────────┘   │
│                  │                                                    │
│                  │  Showing 1-10 of 47 jobs        [< 1 2 3 4 5 >]   │
└──────────────────────────────────────────────────────────────────────┘
```

#### Components

**Tabs**
- `Tabs`: Active (running only), History (completed/failed), All

**Filters**
- `Select` for retailer (multi-select or single)
- `Select` for status
- `Calendar` date range picker (optional)

**Jobs Table**
- `Table` component
- Columns:
  - Retailer (logo + name)
  - Status (`Badge`)
  - Stores (count, with progress if running)
  - Duration
  - Started (timestamp)
  - Actions (`DropdownMenu`: View, Download, Re-run, Delete)
- Sortable columns (click header)
- Pagination

#### Subframe Components
- `Tabs`
- `Select` (filters)
- `Calendar` (date range)
- `Table`
- `Badge`
- `Progress` (inline for running jobs)
- `DropdownMenu` (row actions)
- `Button` (new job)

---

### Page 6: Browse Stores

**Route**: `/data` or `/data/browse`
**Layout**: `DefaultPageLayout`
**Access**: Authenticated

#### Purpose
Search, filter, and browse store data from completed scrapes.

#### Wireframe
```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR          │  MAIN CONTENT                                     │
│                  │                                                    │
│                  │  Store Data                                        │
│                  │                                                    │
│                  │  [Tabs: Browse | Map | Changes ]                   │
│                  │                                                    │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │ Search: [________________] [Search]        │   │
│                  │  │ Filters: [Retailer ▼] [State ▼] [City ▼]  │   │
│                  │  └────────────────────────────────────────────┘   │
│                  │                                                    │
│                  │  Showing 4,847 stores                [Download ▼] │
│                  │                                                    │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │ Table                                      │   │
│                  │  │ Retailer|Name|Address|City|State|Phone|... │   │
│                  │  │ ─────────────────────────────────────────  │   │
│                  │  │ Verizon |Store #123|123 Main St|SF|CA|...  │   │
│                  │  │ AT&T    |Downtown  |456 Oak Ave|LA|CA|...  │   │
│                  │  │ ...                                        │   │
│                  │  └────────────────────────────────────────────┘   │
│                  │                                                    │
│                  │  [< 1 2 3 ... 485 >]                               │
└──────────────────────────────────────────────────────────────────────┘
```

#### Features

**Search**
- `TextField` for full-text search across store name, address, city
- Search button or enter to search

**Filters**
- `Select` (multi): Retailer
- `Select` (multi): State
- `Select`: City (populated based on state selection)
- Clear filters button

**Results Table**
- `Table` with columns: Retailer, Store Name/ID, Address, City, State, ZIP, Phone, Coordinates, Last Updated
- Sortable columns
- Click row → show store detail in `Drawer`
- Pagination (server-side for large datasets)

**Download**
- `DropdownMenu` button with format options:
  - Download as JSON
  - Download as CSV
  - Download as Excel
  - Download as GeoJSON
- Downloads filtered/searched results

#### Subframe Components
- `Tabs`
- `TextField` (search)
- `Select` (filters, multi-select support)
- `Table`
- `Badge` (retailer)
- `DropdownMenu` (download options)
- `Button`
- `Drawer` (store detail)

---

### Page 7: Map View

**Route**: `/data/map`
**Layout**: `DefaultPageLayout`
**Access**: Authenticated

#### Purpose
Geographic visualization of store locations.

#### Wireframe
```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR          │  MAIN CONTENT                                     │
│                  │                                                    │
│                  │  Store Data                                        │
│                  │                                                    │
│                  │  [Tabs: Browse | Map | Changes ]                   │
│                  │                                                    │
│                  │  Filters: [Retailer ▼] [State ▼]    [Download ▼]  │
│                  │                                                    │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │                                            │   │
│                  │  │                 MAP                        │   │
│                  │  │           (Mapbox/Leaflet)                 │   │
│                  │  │                                            │   │
│                  │  │     📍 📍    📍                             │   │
│                  │  │        📍 📍 📍 📍                          │   │
│                  │  │                                            │   │
│                  │  └────────────────────────────────────────────┘   │
│                  │                                                    │
│                  │  Showing 4,847 stores (clustered at this zoom)    │
└──────────────────────────────────────────────────────────────────────┘
```

#### Features
- Interactive map (Mapbox GL JS or Leaflet recommended)
- Cluster markers at low zoom levels
- Individual pins at high zoom
- Click pin → popup with store info
- Filter by retailer (color-coded pins)
- Filter by state/region

#### Technical Notes
- Map component is external (not Subframe) — integrate via custom component
- Use GeoJSON data from scraper output
- Consider performance for large datasets (clustering required)

---

### Page 8: Change History

**Route**: `/data/changes`
**Layout**: `DefaultPageLayout`
**Access**: Authenticated

#### Purpose
View differences between scrape runs — new stores, closed stores, updated info.

#### Wireframe
```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR          │  MAIN CONTENT                                     │
│                  │                                                    │
│                  │  Store Data                                        │
│                  │                                                    │
│                  │  [Tabs: Browse | Map | Changes ]                   │
│                  │                                                    │
│                  │  Compare: [Verizon ▼]  [Jan 27 ▼] vs [Jan 20 ▼]   │
│                  │                                                    │
│                  │  Summary                                           │
│                  │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│                  │  │ + 12     │ │ - 3      │ │ ~ 47     │           │
│                  │  │ New      │ │ Closed   │ │ Updated  │           │
│                  │  └──────────┘ └──────────┘ └──────────┘           │
│                  │                                                    │
│                  │  [Tabs: New Stores | Closed | Updated ]            │
│                  │                                                    │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │ Table of new stores...                     │   │
│                  │  └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

#### Features
- Select retailer and two dates to compare
- Summary cards: New, Closed, Updated counts
- Tabbed detail view for each change type
- Leverage existing `change_detector.py` backend

#### Subframe Components
- `Select` (retailer, dates)
- `Tabs` (change types)
- `Table` (change details)
- `Badge` (change type indicators)

---

### Page 9: Downloads

**Route**: `/downloads`
**Layout**: `DefaultPageLayout`
**Access**: Authenticated

#### Purpose
Central location to download data files from completed jobs.

#### Wireframe
```
┌──────────────────────────────────────────────────────────────────────┐
│ SIDEBAR          │  MAIN CONTENT                                     │
│                  │                                                    │
│                  │  Downloads                                         │
│                  │                                                    │
│                  │  Filter: [Retailer ▼] [Format ▼]                  │
│                  │                                                    │
│                  │  ┌────────────────────────────────────────────┐   │
│                  │  │ Table                                      │   │
│                  │  │ Retailer | Date | Stores | Format | Size   │   │
│                  │  │ ─────────────────────────────────────────  │   │
│                  │  │ Verizon  | Jan 28 | 2,756 | JSON  | 4.2MB │⬇  │
│                  │  │ Verizon  | Jan 28 | 2,756 | CSV   | 1.8MB │⬇  │
│                  │  │ AT&T     | Jan 27 | 2,847 | JSON  | 4.5MB │⬇  │
│                  │  │ ...                                        │   │
│                  │  └────────────────────────────────────────────┘   │
│                  │                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

#### Subframe Components
- `Select` (filters)
- `Table`
- `Badge` (format type)
- `IconButton` (download action)

---

### Page 10: Settings (Admin Only)

**Route**: `/settings`
**Layout**: `DefaultPageLayout`
**Access**: Admin only

#### Sub-pages via tabs or sidebar sub-nav:

#### 10a. Scraper Configuration
- Proxy settings (`TextField` for endpoint, `Switch` for enabled)
- Default concurrency (`Slider`)
- Timeout settings (`TextField` numeric)
- Rate limit configuration

#### 10b. Retailers
- `Table` of supported retailers
- Enable/disable retailers (`Switch`)
- Add new retailer (admin, future feature)

#### 10c. Users
- `Table` of users: Email, Role, Last Active, Status
- Invite new user (`Dialog` with email input + role `Select`)
- Change role (`Select` inline or via `DropdownMenu`)
- Deactivate user

#### 10d. Retention Policy
- Rolling retention: `TextField` for number of runs to keep per retailer
- `Button` to manually trigger cleanup

#### Subframe Components
- `Tabs` or nested sidebar navigation
- `TextField`, `Switch`, `Slider` (configuration)
- `Table` (users, retailers)
- `Select` (role selection)
- `Dialog` (invite user)
- `Button`

---

## Global Components

### Sidebar Navigation

```
[Logo]

○ Dashboard
○ Jobs
○ Data
○ Downloads

─────────────
ADMIN (if admin role)
○ Settings

─────────────
[Avatar] User Name
        Role
        [•••] → Profile, Log out
```

- Use `SidebarWithSections` component
- Highlight current page
- Show admin section only for admin users
- User dropdown in footer with `DropdownMenu`

### Toast Notifications

Global toast system for:
- Job started confirmation
- Job completed (success)
- Job failed (error)
- Download ready
- Settings saved

Use `Toast` component with appropriate variants.

### Email Notifications (Backend)

Send emails for:
- Magic link login
- Job completed (configurable per user)
- Job failed (configurable per user)

---

## Technical Requirements

### Real-time Communication
- **WebSocket** connection for:
  - Job progress updates
  - Live log streaming
  - Error events
  - Job state changes (started, completed, failed)

### API Endpoints (FastAPI Backend)

```
Authentication:
POST   /auth/magic-link          Request magic link
GET    /auth/verify              Verify magic link token
POST   /auth/logout              Logout

Jobs:
GET    /jobs                     List jobs (with filters)
POST   /jobs                     Create new job
GET    /jobs/:id                 Get job detail
DELETE /jobs/:id                 Stop/cancel job
WS     /jobs/:id/stream          WebSocket for live updates

Data:
GET    /stores                   List stores (with search/filters)
GET    /stores/export            Download stores (format param)
GET    /stores/changes           Get change comparison
GET    /stores/geojson           GeoJSON for map

Downloads:
GET    /downloads                List available downloads
GET    /downloads/:id            Download file

Settings (Admin):
GET    /settings                 Get all settings
PUT    /settings                 Update settings
GET    /users                    List users
POST   /users/invite             Invite user
PUT    /users/:id                Update user
DELETE /users/:id                Deactivate user
GET    /retailers                List retailers
PUT    /retailers/:id            Update retailer config
```

### Data Retention
- Keep last N runs per retailer (admin-configurable, default: 10)
- Automatic cleanup job (cron or on-demand)
- Include run metadata: timestamp, store count, duration, status

---

## Implementation Phases

### Phase 1: Core MVP
1. Authentication (magic link)
2. Dashboard (basic stats, active jobs)
3. New Job dialog (retailer selection, basic options)
4. Job monitoring (progress, status)
5. Downloads page

### Phase 2: Data Browsing
1. Browse stores table with search/filter
2. Store detail drawer
3. Export functionality

### Phase 3: Advanced Features
1. Map visualization
2. Change detection/comparison view
3. Full settings panel
4. User management

### Phase 4: Polish
1. Email notifications
2. Nice-to-have monitoring (resource usage, checkpoints)
3. Performance optimization
4. Mobile responsiveness

---

## Appendix: Component Props Reference

### Badge Variants
- `success` — Green, completed/online
- `warning` — Yellow, retrying/degraded
- `error` — Red, failed/offline
- `neutral` — Gray, pending/unknown

### Button Variants
- `brand-primary` — Primary actions (Start Job, Save)
- `brand-secondary` — Secondary actions
- `neutral-secondary` — Cancel, Close
- `destructive-primary` — Delete, Stop Job
- `destructive-secondary` — Destructive but less prominent

### Alert Variants
- `success` — Operation completed
- `warning` — Caution/attention needed
- `error` — Error occurred
- `neutral` — Informational

---

*Document optimized for Subframe design-to-code workflow. Each page specification maps to a Subframe page with listed components.*
