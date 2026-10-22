# The assistant

The assistant answers questions about the BeCoMe method, about your projects and about how to use
the app. It is an AI language model, not a person, and its answers can be wrong. Treat what it says
as a starting point, and check anything that matters on the result page and in this documentation.

## Where to find it

Sign in and click the assistant button in the top bar. It is a sparkle icon, and **Assistant**
appears when you hover over it.

On a project's page, both that button and **Explain this result** on the result page open the panel
for the project, and the panel header shows the project's name. Anywhere else in the app the panel
is labelled **Method and app**. It has no project to look at there, so it answers questions about
the method and about using BeCoMe.

## What it can answer

**The method.** How fuzzy opinions work, how the best compromise is computed, what the maximum
error says. These are the questions the pages on this site answer too, so the assistant is mostly a
faster way to the right paragraph.

**Your project.** Its opinions and its result, for example why the confidence is Moderate. The
assistant sees only what you see as a member of that project. Every question you send from a
project's panel carries that project's data, whatever the question is about. [Your data](#your-data)
says what that includes.

**The app.** How to create a project or invite experts. This works without a project selected.

The assistant only reads. It cannot change a project, an opinion or your account.

## Limits

You can send up to 60 messages an hour. When you reach the limit, the assistant says how many
minutes to wait.

An answer can take up to a minute.

In a long conversation, older messages are no longer sent with new questions, and the panel marks
the point where that starts. The assistant stops taking those messages into account, so repeat
anything it needs to know.

## When something goes wrong

**Message limit reached.** You have used your 60 messages for this hour. The hour starts with your
first message. Wait the number of minutes the message shows.

**The assistant is temporarily unavailable.** The assistant is busy or the model is not responding.
Try again in a few minutes.

**This project is not available.** The project was deleted, or you are no longer a member. The
message offers two buttons. **Ask without the project** switches to the **Method and app** panel,
where you can ask again. **Open projects** closes the panel and takes you to your projects list.

**The connection dropped.** The part of the answer that arrived stays on screen. Pressing **Stop**
does the same and marks the answer as stopped. Either way the partial answer is not sent with your
next question. Under an error, **Try again** sends the question once more.

An orange warning under an answer means the assistant wrote numbers it could not match to the
documentation or to your project's data. Do not rely on those numbers until you have found them on
the result page.

## What is kept

The conversation lives in your browser tab and nowhere else. It is not saved to your account or on
the server. Closing the tab erases it, and so does signing out. Reloading the tab keeps it.

Each project has its own conversation, and the **Method and app** panel has a separate one.
**Clear conversation** erases only the one that is open. A confirmation appears first, because this
cannot be undone.

## Your data

To answer, the assistant sends your question and the data of the open project to an AI model in the
EU. That data includes other members' names, positions and opinions, since the project belongs to
all of them. [What the assistant sends](security.md#what-the-assistant-sends) lists it field by
field, and the [Privacy notice](https://www.becomify.app/privacy) covers how long each part is kept.

If you do not want other members' assistant to show your opinions, turn on **Hide my opinions from
other members' assistant** in your profile. It still shows them to you. The project result is
calculated as before and still includes your opinion.

The switch has two limits. If no one else in the project has hidden theirs, your values can be
worked out from the result and the other opinions. The assistant is told not to do that
calculation. Other members may also notice that one opinion is missing.

Do not type sensitive data into the assistant, such as health information or other people's contact
details.

Next: [a worked example](worked-example.md), where the four figures of a result come from a real
panel of thirteen.
