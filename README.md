# MeetConfirm

**MeetConfirm is a personal, cost-free service for automatically confirming meetings scheduled via Google Calendar and notifying through Gmail.**

It was created as a practical tool for founders and product teams who use tools like Firebase In-App Messaging to schedule user interviews and demos. As Sam Altman might describe it, MeetConfirm is like "fast fashion SaaS": simple, useful, and nearly cost-free to operate.

### Executive Summary

*   **What it is:** A serverless, open-source tool that automatically sends confirmation emails for Google Calendar events and cancels them if not confirmed.
*   **Who it's for:** Founders, product managers, and researchers who schedule meetings at scale and need to reduce no-shows.
*   **Why it's unique:** It's a showcase of a vertically integrated Google Cloud solution, designed to be deployed in 15 minutes and run for virtually free.

### Onboarding and Confirmation Flow

| Welcome Email | Confirmation Request |
| :---: | :---: |
| ![Welcome Email](images/intro%20email.png) | ![Confirmation Email](images/confirmation%20email.png) |

## The Google Vertical Chain

MeetConfirm is a powerful example of a "vertical chain" application built entirely on the Google Cloud stack. Each service seamlessly hands off to the next, creating a robust, automated workflow with minimal overhead.

```mermaid
graph TD
    subgraph User Interaction
        A[Firebase In-App/Email] -- User books a meeting --> B(Google Calendar);
    end
    subgraph Automated Backend
        B -- Event Created Webhook --> C{MeetConfirm on Cloud Run};
        C -- 1. Create Event State --> D[Firestore];
        C -- 2. Schedule Timers --> E[Cloud Tasks];
        E -- T-2 hours --> C -- 3. Trigger Confirmation --> C;
        C -- 4. Send Email --> F(Gmail API);
    end
    style C fill:#4285F4,stroke:#fff,stroke-width:2px,color:#fff
    style F fill:#DB4437,stroke:#fff,stroke-width:2px,color:#fff
    style B fill:#0F9D58,stroke:#fff,stroke-width:2px,color:#fff
    style D fill:#F4B400,stroke:#fff,stroke-width:2px,color:#fff
    style E fill:#F4B400,stroke:#fff,stroke-width:2px,color:#fff
```

This architecture demonstrates how to build a sophisticated, event-driven system without managing a single server or database cluster.

## Feature Highlights

*   **Automated Confirmations & Cancellations:** Reduce no-shows and administrative overhead.
*   **Deep Google Cloud Integration:** A showcase of Cloud Run, Cloud Tasks, Secret Manager, Firestore, Google Calendar, and Gmail.
*   **15-Minute Deployment:** Get up and running quickly with a single script.
*   **Open Source:** MIT licensed and fully transparent.

## Economic Model

MeetConfirm is designed to be virtually free for most real-world scenarios by leveraging the generous free tiers of Google Cloud services.

| Service          | Free Tier Limit        | Approx. Daily Capacity (Free) |
| ---------------- | ---------------------- | ----------------------------- |
| Cloud Run        | 2,000,000 reqs/month   | ~66,000 requests/day          |
| Firestore        | 50,000 reads/day       | ~6,000 bookings/day           |
| Cloud Tasks      | 500,000 tasks/month    | ~16,000 tasks/day             |
| Gmail API        | 2,000 emails/day (user)| 2,000 confirmations/day       |
| Calendar API     | 1,000,000 reqs/day     | Ample headroom                |
| Secret Manager   | 10,000 ops/month       | Ample headroom                |

**Estimated Costs:**
*   **≤ 1,000 meetings/day:** ≈ $0
*   **10,000 meetings/day:** < $10/month

## Stack Summary

| Component        | Purpose                               | Free Tier        | Notes                                     |
| ---------------- | ------------------------------------- | ---------------- | ----------------------------------------- |
| **Cloud Run**    | Core FastAPI application             | 2M reqs/mo       | Handles API endpoints and webhooks.       |
| **Firestore**    | Store event state (pending/confirmed) | 50k reads/day    | Simple, scalable, and cost-effective.     |
| **Cloud Tasks**  | Scheduler for delayed actions         | 500k tasks/mo    | Used for confirmation and cancellation timers. |
| **Gmail API**    | Send confirmation emails              | 2k/day per user  | Easily extendable with other email providers. |
| **Calendar API** | Watch for new events and cancel them  | 1M reqs/day      | The core of the event detection system.   |
| **Secret Manager**| Securely store credentials          | 10k ops/mo       | Manages OAuth tokens and signing keys.    |

---

**Maintainer:** Michal Barodkin (Blatt sp. z o.o., Warsaw)  
*Founder at [HeartScan](https://heartscan.app) & Alumnus of [Google for Startups Campus, Warsaw](https://www.campus.co/warsaw/)*  
**Contact:** michal.b@heartscan.app  
*Built with Gemini 2.5 Pro + Cline (AI-assisted coding)*

---

For deployment instructions, see [DEPLOY.md](DEPLOY.md).  
For a detailed look at the internal logic, see [ARCHITECTURE.md](ARCHITECTURE.md).
