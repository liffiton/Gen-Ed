---
title:  Data Protection Impact Assessment (DPIA)
summary:  A formal assessment of how CodeHelp processes user data.  Part of GDPR compliance.
category:  Privacy
---

# Data Protection Impact Assessment (DPIA) for CodeHelp

## 1. Introduction

### 1.1 System Overview and Purpose

CodeHelp is an educational web application designed to provide students with
AI-assisted coding and computer science support. The system processes personal
data for the following purposes:

1. to authenticate users and manage access control
2. to enable instructors to monitor student usage of the application

### 1.2 Need for a DPIA

This DPIA is being conducted because children, who are considered "vulnerable
data subjects," may potentially use CodeHelp.

## 2. Description of Processing Operations

### 2.1 Data Processing Activities

#### Personal Data Collection

The application collects basic user identification information, including name,
email address, and username. Additionally, it gathers authentication tokens/IDs
from third-party authentication providers, such as Google, Microsoft, GitHub,
or a learning management system (LMS). Class membership and role assignments
are also recorded. The system logs user queries and the history of their
interactions with the AI. No special categories of data are processed.

#### Data Flows

The data flow within CodeHelp can be broken down into two primary categories:
authentication and educational processing.

1. **Authentication:**
    * Users authenticate through third-party providers.
    * CodeHelp stores only essential authentication data and basic profile
      information: name, email address, and username.
    * Passwords are not collected or stored for regular users.
2. **Educational Processing:**
    * Students submit coding questions through the application.
    * These queries are processed via the OpenAI API, which retains data for a
      maximum of 30 days and does not use it for training its models.
    * The responses generated are stored along with user identification
      information. This allows users to reference their interactions and
      enables instructor oversight.
    * Instructors can access student data, but only within the classes to which
      they are assigned.

### 2.2 Scope and Scale

CodeHelp anticipates approximately 1,000 monthly active users and is not
engaged in large-scale data processing. The user base may include school-age
students (children). When students use CodeHelp, their usage is under the
direction and oversight of their teacher.

Data is stored on CodeHelp's server, which is located in the United States.
Data processing is limited to the educational context, and there is no
automated decision-making beyond the AI assistance provided. The system does
not engage in profiling or behavioral analysis, and no personal data is shared
with third parties.

### 2.3 Technical and Security Measures

CodeHelp employs a variety of technical and security measures to protect user
data. These include secure third-party authentication and a role-based access
control system. Communication is encrypted using HTTPS/TLS, and data storage
and backups are encrypted using industry-standard tools with the AES encryption
algorithm. The system undergoes regular security updates and monitoring. Data
retention is limited to two years after the last user activity.

## 3. Necessity and Proportionality Assessment

### 3.1 Necessity Analysis

The data processing operations are necessary to securely identify users, manage
access to the application, and ensure that instructors can effectively oversee
student usage.

### 3.2 Proportionality Analysis

CodeHelp adheres to data minimization principles. Only essential personal data
is collected. Authentication is handled through trusted third parties. Data
retention periods are limited, and access is restricted based on educational
need. There are no secondary uses of personal data, and no automated profiling
or decision-making takes place.

### 3.3 Legal Basis

The legal basis for processing data is the "legitimate interest" in using it to
provide educational support and instructor oversight. Processing minimal
personal data is necessary for instructors to be able to identify their
students and connect queries to individual students.

### 3.4 Data Subject Rights

Users can exercise their data subject rights through several methods. The
account management interface provides data export capabilities, as well as
account anonymization and deletion options. Users can also contact
administrators directly. A clear privacy policy and information are provided to
ensure transparency.

## 4. Risk Assessment

### 4.1 Identified Risks

The following risks to data subject rights and freedoms have been identified:

1. **Unauthorized Access:** There is a potential for unauthorized access to
   student queries and usage history. Additionally, there is a risk of
   credential compromise through third-party authentication providers. There is
   also the possibility of an instructor role being misassigned.
2. **Data Breach:** This includes the potential for a backup security
   compromise or a server compromise.

### 4.2 Risk Analysis

**Unauthorized Access**

* **Likelihood:** Remote. The system employs strong authentication controls
  through trusted major providers. Clear role-based access controls are in
  place, and users are only assigned the instructor role for classes they
  created themselves or in which another instructor granted them the role.
* **Severity:** Medium. Unauthorized access to a student's queries by a peer
  may reveal usage patterns or learning difficulties, potentially leading to
  emotional and psychological harm. Otherwise, the severity is mitigated by the
  fact that minimal personal data is collected, and no financial or sensitive
  personal data or special category data are involved.
* **Overall Risk:** Low

**Data Breach**

* **Likelihood:** Low. Industry-standard server security processes are
  followed, and strong encryption is used in communication channels and backup
  storage.
* **Severity:** Minor. The severity is mitigated by the fact that minimal
  personal data is collected, and no financial or sensitive personal data or
  special category data are involved.
* **Overall Risk:** Low

## 5. Measures to Address Risks

### 5.1 Technical Measures

1. **Access Control:** CodeHelp utilizes third-party authentication with
   trusted providers and a role-based access control system. Session management
   and timeout controls are implemented, and regular access reviews and
   monitoring are conducted.
2. **Data Security:**  Communication between the client and server, as well as
   between the server and third-party authentication and API providers, is
   encrypted. Data storage and backups are also encrypted, and the system
   receives regular security updates.
3. **Opt-Out Measures:** Instructors have the ability to create classes in
   which registering students are anonymous (given a randomized username), with
   no personal data stored. Users also have the option to anonymize their
   account while retaining access.

### 5.2 Residual Risk Assessment

After implementing the measures described above, the residual risks are
considered acceptable. This assessment is based on the implementation of strong
technical controls, the limited scope of data collection, and the necessity of
the processing within the educational context.

