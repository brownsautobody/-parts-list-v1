# parts-list-v1

## Project Prompt

Auto Body Shop Database System — Project Overview
Business Need

Build a centralized database system for [Shop Name] to manage all job information, documentation, and shop operations. Currently, job data is scattered across estimate PDFs, spreadsheets, and email. This system will become the single source of truth for all shop operations.

Long-Term Vision (Full System)

The completed system will:

Centralize all job data — estimates, labor, parts, status, documents (invoices, communications, photos)
Feed downstream tools that shop staff use daily:
Parts receiving document (updates inventory, links to jobs)
Production/shop board (shows job status in real-time)
Job tracking/archival (completed and archived jobs)
Customer communications and invoicing
Enable data-driven decisions — job profitability, turnaround time, parts costs, etc.
Phase 1: PDF Extraction & Data Display (THIS SPRINT)

Goal: Build a PDF ingestion tool that can reliably extract estimate data and display it in a structured format.

Scope:

Upload estimate PDF from [estimating software]
Extract relevant data:
Customer name and contact info
Vehicle info (year, make, model, VIN)
Labor line items (description, hours, rate, total)
Parts line items (description, quantity, unit price, total)
Estimate totals (labor, parts, other, grand total)
Display extracted data in a clean table format
Validate accuracy and identify parsing issues

Deliverable:

Working tool that reliably parses estimate PDFs and displays results
Code is modular so the parser can be reused when building the database later

Success Criteria:

Correctly extracts 90%+ of data from a sample estimate PDF
Handles formatting variations in the estimate document
Easy to iterate on if extraction misses anything
Phase 2 & Beyond (Future)
Create database schema based on extracted data structure
Build REST API for job CRUD operations
Integrate PDF parser into job creation workflow
Add document storage (linking files to jobs)
Build production board and parts receiving tools
Add user permissions and audit logging
Technical Approach
Language: Python (for fast iteration)
PDF parsing: [pdfplumber/PyPDF2]
Display: HTML table for MVP (can upgrade to web interface later)
Storage: Git repo, pushing incrementally
Next step: Once parsing is solid, create database schema to match this data structure

