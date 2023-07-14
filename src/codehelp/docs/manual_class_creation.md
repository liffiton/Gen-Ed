title:  Manual Class Creation
summary:  How to create a class "manually," logging in with a Google, Github, or Microsoft account.


# Manual Class Creation

<p class="notification is-info"><b>Note:</b> We recommend using an LTI connection from your LMS over this manual approach.  Creating and sharing a class manually from CodeHelp has some drawbacks compared to LTI.  It is an alternative for cases where LTI is not an option.</p>

These instructions explain how to create and share a class manually.
Compared to connecting via LTI, this has the following drawbacks:

  1. Every user (student and instructor) must log in to CodeHelp with a Google, Github, or Microsoft account.  <i>[LTI handles authentication automatically.]</i>
  2. A class can only have one instructor (the user who creates it).  <i>[An LTI connection automatically gives any instructor or TA instructor-level access in CodeHelp.]</i>
  3. Students will be identified by their login account and the name registered to it.  This may not correspond to their school email or the name they use in class.  <i>[LTI provides institution email addresses and names from your LMS.]</i>

## Creation

First, log in to CodeHelp using a Google, Github, or Microsoft account.
Whatever account you use to connect will be the account registered as an "instructor" for the new class.

Once logged in, go to your <a href="/profile/">profile page</a> (also accessible by clicking on your user info in the navigation bar at the top of the page).

Under the "Classes" heading, press "Create new class."
This will bring up a dialog asking for a class name and an OpenAI API key.

The OpenAI API key will be used for your students' queries in CodeHelp.
You can create an API key using an account at <a href="https://openai.com/">openai.com</a>.
OpenAI will charge you directly for your students' usage, so you will need to provide them a credit card to bill.
The cost is low.
One query from CodeHelp costs roughly US$0.002 (two tenths of a cent).

## Configuration

After submitting the new class form, you will be brought to the configuration screen for the class you created.
Here, you will see an <b>access/join link</b> that can be shared with your students.
Anyone using the link will register as a student in the class if "Registration via Link" is enabled.
You can control whether registration is allowed by manually enabling and disabling it or by setting a date up until which registration will be enabled.
Once they have registered, students can use the same link to access CodeHelp and make queries connected to your class.

Before your students can use CodeHelp, you will need to provide a configuration under "Queries &amp; Responses," at least selecting a default language.

In the configuration screen, you can also archive the class (so students can see their past queries but not make new ones) and change the OpenAI API key you have connected to it.

## Managing Classes

Only one class can be active at a time.
If you have multiple classes in CodeHelp, you can switch between them from your user profile page.

If you are an instructor for the currently active class, you will have links to the class configuration page and the instructor view in your navigation bar.
