---
title:  Manual Class Creation
summary:  How to create a class "manually," logging in with a Google, Microsoft, or Github account.
---

# Manual Class Creation

<p class="notification is-info"><b>Note:</b> We recommend using an LTI connection from your LMS over this manual approach.  Creating and sharing a class manually from CodeHelp has some drawbacks compared to LTI.  However, manual creation is faster, and it is an alternative for cases where LTI is not an option.</p>

These instructions explain how to create and share a class manually.
Compared to connecting via LTI, this has the following drawbacks:

1. Every user (student and instructor) must log in to CodeHelp with a Google, Microsoft, or Github account.  <i>[LTI handles authentication automatically.]</i>
2. Additional instructors (beyond the user who creates the class) must be manually assigned after they have joined the class.  <i>[An LTI connection automatically gives any instructor or TA instructor-level access in CodeHelp.]</i>
3. Students will be identified by their login account and the name registered to it.  This may not correspond to their school email or the name they use in class.  <i>[LTI provides institution email addresses and names from your LMS.]</i>

## Creation

First, log in to CodeHelp using a Google, Microsoft, or Github account.
Whatever account you use will be registered as an "instructor" for the new class.

Once logged in, go to your <a href="/profile/">profile page</a> (also accessible by clicking on your user info in the navigation bar at the top of the page).

In the "Classes" section, press "Create new class."
This will bring up a dialog asking for a class name and an OpenAI API key.

The OpenAI API key will be used for your students' queries in CodeHelp.
If you don't have an API key yet, you can leave it blank for now, but it will be required for anyone to submit queries in your class.
You can create an API key using an account at <a href="https://openai.com/">openai.com</a>.
OpenAI will charge you directly for your students' usage, so you will need to purchase usage credits using a credit card.
The cost is low.
One query from CodeHelp costs roughly US$0.01 if using GPT-4o (the recommended model) or $0.0004 using GPT-4o-mini (which is less accurate).

## Configuration

After submitting the new class form, you will be brought to the configuration screen for the class you created.
Here, you will see an <b>access/join link</b> that can be shared with your students.
Anyone using the link will register as a student in the class if "Registration via Link" is enabled.
You can control whether registration is allowed by manually enabling and disabling it or by setting a date up through which registration will be enabled.
Once students have registered, they can use the same link to access CodeHelp and make queries connected to your class.

In the configuration screen, you can also archive the class (so students can see their past queries but not make new ones) and change or delete the OpenAI API key you have connected to it.

## Adding Instructors

To add instructors to the course, you can give other users the "instructor" role in your class.
First, have them join the class via the "Access/Join Link" found in the class configuration screen.
Then, to give them the instructor role, go to the instructor view and check the box in the "Instructor?" column for their user in the Users table.

## Switching Between Classes

If you have multiple classes in CodeHelp, you can switch between them using a drop-down menu under the profile link in the navigation bar or from your user profile page.
When you have selected a class in which you are an instructor, the navigation bar will contain links to its class configuration and instructor view pages.
