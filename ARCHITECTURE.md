# MeetConfirm Architecture

This document provides a technical overview of the MeetConfirm application's internal architecture, its components, and the design decisions behind them.

## Core Components

The application is built around a modular structure, with responsibilities separated into distinct services.

*   **`endpoints.py`:** The main API layer, built with FastAPI. It handles all incoming HTTP requests, including webhooks from Google Calendar, user-facing confirmation/cancellation links, and administrative endpoints like `/setup-calendar-watch`. It orchestrates the other services to perform the required actions.

*   **`calendar.py`:** A service module dedicated to all interactions with the Google Calendar API. It handles authentication, watching for changes, listing events, and deleting events.

*   **`email.py`:** A service module for sending emails via the Gmail API. It uses Jinja2 templates to render HTML emails for confirmations and cancellations.

*   **`tasks.py`:** A service module for interacting with Google Cloud Tasks. It encapsulates the logic for creating and scheduling delayed tasks, which are used to trigger confirmation emails and enforce deadlines.

## Key Services and Their Roles

*   **Firestore:** Used as a lightweight, serverless database to maintain the state of each meeting (`pending`, `confirmed`, `cancelled`). Its simplicity and generous free tier make it a perfect choice for this use case, avoiding the complexity of a traditional SQL database.

*   **Cloud Tasks:** The scheduling engine of the application. When a new event is detected, Cloud Tasks is used to schedule two future actions:
    1.  Send the confirmation email (e.g., 2 hours before the meeting).
    2.  Enforce the confirmation deadline (e.g., 1 hour before the meeting).
    This is a more robust and cost-effective solution than using `time.sleep` or a persistent scheduler process.

## The Lifecycle of an Event

1.  **Detection:** A new event is created in Google Calendar. Because the `/setup-calendar-watch` endpoint was called on deployment, Google sends a webhook notification to the `/webhook/calendar` endpoint on our Cloud Run service.

2.  **State Creation:** The application receives the webhook, fetches the event details from the Calendar API, and creates a new document in Firestore with the event's ID and a status of `pending`.

3.  **Task Scheduling:** Two tasks are created in Cloud Tasks:
    *   A `send-confirm` task, scheduled to run at `T-2 hours` before the meeting.
    *   An `enforce` task, scheduled to run at `T-1 hour` before the meeting.

4.  **Confirmation Email:** When the `send-confirm` task executes, it calls the `/tasks/send-confirm/{event_id}` endpoint. This function fetches the event details, generates the confirmation and cancellation links, and sends the email via the Gmail API. The event's status in Firestore is updated to `confirmation_sent`.

5.  **User Action:**
    *   **If the user clicks "Confirm":** They are taken to the `/confirm` endpoint. The application verifies the token, updates the event's status in Firestore to `confirmed`, and displays a confirmation page.
    *   **If the user clicks "Cancel":** They are taken to the `/cancel` endpoint. The application deletes the event from Google Calendar and updates its status in Firestore to `cancelled_by_user`.

6.  **Deadline Enforcement:** When the `enforce` task executes, it calls the `/tasks/enforce/{event_id}` endpoint. It checks the event's status in Firestore. If the status is still `confirmation_sent` (meaning the user did not confirm), the application calls the Google Calendar API to delete the event and updates the status in Firestore to `cancelled_by_system`.

## Design Decisions

*   **Why not Pub/Sub?** While Pub/Sub is a powerful messaging service, it would be overkill for this application. Cloud Tasks provides the simple, scheduled, "at-least-once" delivery needed for the confirmation and enforcement logic without the added complexity of a message bus.

*   **Why Firestore over Cloud SQL?** The application's data model is very simple: a key-value store for event states. Firestore's document model is a natural fit, and its serverless nature, automatic scaling, and generous free tier make it more cost-effective and easier to manage than a relational database like Cloud SQL for this specific use case.

---

For a high-level overview of the project, see [README.md](README.md).  
For deployment instructions, see [DEPLOY.md](DEPLOY.md).
