
You are working inside an existing vocabulary-learning web application.

The existing website already has:

* vocabulary word lists
* English words
* Chinese definitions/translations
* dictionary/explanation data
* user familiarity/mastery tracking
* book-based vocabulary lists
* existing navigation/panels/pages

Your task is to add a new vocabulary-learning game as a new panel/page inside the existing website.

Do NOT rebuild the application from scratch.
Do NOT unnecessarily refactor unrelated code.
First inspect the existing project structure, frontend framework, routing/navigation, styling system, vocabulary data model, and mastery update logic. Reuse existing components, APIs, types, and design patterns wherever possible.

# Feature name

Use a suitable name such as:

"Word Shooter"

Add it as a new panel/menu/navigation item alongside the existing vocabulary features.

# Core concept

This is a simple 2D browser shooting game for learning unfamiliar English vocabulary.

The question shown to the player is a Chinese meaning/definition.

Several enemy airplanes move across the game area. Each airplane displays one English word.

The player must shoot/click the airplane containing the English word that matches the Chinese meaning.

Example:

Question:
奇怪的；不寻常的

Enemy airplanes:

* peculiar
* reluctant
* gaze

Correct answer:
peculiar

The primary purpose is LEARNING NEW WORDS, not merely testing words the user already knows.

# MVP scope

Build a clean, playable MVP first.

Do not add complicated maps, RPG systems, accounts, equipment, shops, storylines, or elaborate animations.

The MVP should contain:

1. Game panel
2. Word selection
3. Intro/learning phase for unfamiliar words
4. Shooting gameplay
5. Correct-answer feedback
6. Wrong-answer learning feedback
7. Repetition of difficult words
8. Simple session summary
9. Integration with the site's existing mastery/familiarity data

# Game setup

When entering Word Shooter, allow the player to choose vocabulary from existing website data.

Prefer reusing whatever selection UI/data flow already exists.

Possible sources:

* current vocabulary list
* a selected book vocabulary list
* due/review words
* unfamiliar/new words

For the first version, a session can contain approximately 5–10 vocabulary words.

If the existing application already knows familiarity/mastery, prioritize unfamiliar or low-mastery words.

# Important learning design

Many words may be completely new to the player.

Therefore, DO NOT immediately test completely unknown words without introducing them.

Each session should begin with a short "Discover" phase.

Introduce approximately 3 words at a time.

For each new word briefly show:

English word
Chinese meaning
optional English definition if available
optional example sentence if already available in the site's dictionary data
pronunciation/audio only if the application already has an easy existing way to provide it

Example:

PECULIAR

奇怪的；不寻常的

strange or unusual

A peculiar sound came from the basement.

The player should be able to continue quickly. This phase should feel lightweight, not like reading a long flashcard.

After introducing a few words, begin the shooting round using those words.

Then progressively introduce additional words during the session.

Suggested flow:

Introduce A
Introduce B
Introduce C

Shoot questions involving A/B/C

Introduce D

Shoot questions involving A/B/C/D

Introduce E

Continue mixed review

Final review

# Shooting gameplay

Create a game area using normal web technology.

Prefer the simplest maintainable implementation compatible with the existing project:

* HTML/CSS/React DOM animation is acceptable
* Canvas is acceptable if it clearly simplifies the game
* avoid adding a heavy game engine unless absolutely necessary

Display the Chinese question prominently near the top.

Example:

"不情愿的"

Spawn approximately 3 English-word airplanes in the play area.

Example:

[ peculiar ]    [ reluctant ]    [ gaze ]

Airplanes should move across the screen slowly enough to read.

Desktop:

* clicking an airplane can count as shooting it
* optionally show a projectile animation from the player's cannon toward the clicked airplane

Touch/mobile/tablet:

* tapping an airplane must work well
* targets must be large enough for touch interaction

The game should remain usable on iPad-sized screens.

# Correct answer behavior

If the player shoots the correct airplane:

* destroy/explode/remove the correct airplane
* show clear positive visual feedback
* briefly reinforce the word pair

Example:

RELUCTANT
不情愿的

* award a gameplay reward

For the MVP, use a simple reward such as:

+1 Power Ammo

or

+1 Bonus Shot

The player should always retain a basic way to shoot.

Do NOT allow the player to permanently run out of ammunition and become unable to continue learning.

Bonus ammunition should therefore be a reward/power-up, not a hard requirement to play.

Optionally allow power ammo to:

* create a stronger explosion
* slow enemies briefly
* clear one distractor
* provide another minor visual/gameplay bonus

Keep this simple in the MVP.

# Wrong answer behavior

This is one of the most important learning mechanics.

If the player selects the wrong airplane:

DO NOT simply show "Wrong" and immediately move to the next question.

Instead:

1. visually indicate the selected airplane was wrong
2. make the correct airplane much larger
3. slow or stop the correct airplane
4. prominently show the correct English word
5. show its Chinese meaning directly on or near the airplane
6. optionally show the English definition if space allows
7. require the player to shoot/tap the correct airplane before continuing

Example:

The player incorrectly shoots "reluctant".

Correct airplane becomes:

---

PECULIAR
奇怪的；不寻常的
--------

The player must now shoot PECULIAR.

After the player shoots it, continue the game.

The purpose is:

mistake
→ attention to correct answer
→ active physical selection of correct word
→ reinforcement

A wrong answer should be treated as a learning event, not as punishment.

# Adaptive repetition

Track performance for each word during the session.

At minimum maintain temporary session stats:

* times_shown
* correct_count
* wrong_count
* consecutive_correct
* last_seen
* whether newly introduced

Words answered incorrectly should appear again sooner.

Words consistently answered correctly can appear less frequently.

Use a simple algorithm for MVP.

For example:

* wrong answer: high priority to reappear within the next 2–4 questions
* first correct answer: show again later
* multiple consecutive correct answers: reduce frequency
* do not ask the same word immediately over and over unless necessary

Avoid predictable ordering.

# Difficulty behavior

For unfamiliar/new words:

* larger airplanes
* slower movement
* fewer distractors, perhaps 2–3 choices

For words becoming familiar:

* slightly smaller airplanes
* slightly faster movement
* 3–4 choices

Do not make reading speed the primary difficulty.

The game should test vocabulary memory more than reflexes.

# Distractor selection

Distractors should come primarily from the current session vocabulary pool.

Avoid obviously useless choices when possible.

If existing dictionary metadata includes part of speech, prefer distractors with the same or compatible part of speech.

Do not make the first MVP overly complex if this metadata is not readily available.

Never include the correct word twice.

# Integration with mastery/familiarity

Inspect how the existing website updates word familiarity/mastery.

Reuse that system rather than creating an unrelated permanent scoring model.

The game can maintain session stats internally, then map meaningful results into the existing mastery system.

Suggested relative weighting:

* introduced only: little or no mastery increase
* correct English choice from Chinese: small increase
* repeated correct recall: larger increase
* wrong answer: do not heavily punish; instead schedule earlier repetition
* multiple correct recalls separated in time: meaningful mastery increase

Follow the application's existing conventions if they already exist.

Do not overwrite user data incorrectly.

# Session ending

A session should end after approximately 5–10 words have received sufficient exposure.

Show a simple result screen.

Example:

Word Shooter Complete

Words practiced: 8
Correct shots: 19
Mistakes: 5

Words remembered well:

* peculiar
* gaze
* emerge

Need more practice:

* reluctant
* dreadful

Provide:

Play Again
Return to Vocabulary
Next Session

If appropriate, update the existing mastery state before or when the session completes.

# UI style

Match the existing website's visual design.

Do not create a completely unrelated visual language.

The game itself can feel playful, but the surrounding panel should still look native to the application.

Game screen should have approximately:

Top:

* back/exit
* session progress
* score or correct count
* bonus ammo indicator

Question area:

* large Chinese meaning

Main game area:

* moving English-word airplanes

Bottom:

* optional cannon/player element
* pause/restart only if useful

Use CSS animations or another lightweight approach for:

* airplane movement
* explosion
* correct-answer feedback
* wrong-answer enlargement

Keep animations performant.

# Airplane representation

For MVP, do not spend time sourcing complex game art.

Use one of:

* simple CSS airplane shapes
* emoji/icon
* existing icon library already used by the project
* simple vector/SVG created locally in code

The English word must remain the main visual information.

Example airplane:

```
 ✈
```

[ PECULIAR ]

It is more important that the word is readable than that the airplane looks realistic.

# Architecture

Keep learning logic separate from rendering/game animation.

Create clear components/modules resembling:

WordShooterPanel
WordShooterGame
QuestionDisplay
EnemyPlane
DiscoverCard
SessionSummary

And a learning/session controller such as:

wordShooterSession
or
useWordShooterSession

The controller should decide:

* current learning pool
* which word is being asked
* distractors
* when to introduce a new word
* which difficult word should reappear
* mastery/session updates

The rendering layer should only handle game interaction and presentation.

Use names/styles appropriate to the project's existing architecture rather than blindly using the exact names above.

# State model

A per-word session state could conceptually look like:

{
wordId,
word,
chineseMeaning,
status,
timesShown,
correctCount,
wrongCount,
consecutiveCorrect,
lastSeenAt,
introduced
}

Do not duplicate dictionary content unnecessarily if the project already has normalized vocabulary objects.

# Game state

Conceptually:

{
phase: "discover" | "playing" | "feedback" | "complete",
sessionWords,
activeQuestion,
enemies,
bonusAmmo,
correctShots,
mistakes,
questionIndex
}

Again, adapt to the existing application's state-management approach.

# Important implementation rules

Before coding:

1. Inspect the repository.
2. Identify the frontend stack.
3. Find the navigation/panel system.
4. Find the vocabulary model.
5. Find Chinese definition fields.
6. Find mastery/familiarity logic.
7. Find book vocabulary selection logic.
8. Determine whether tests already exist and follow the project's test conventions.

Then implement the feature using the smallest reasonable change set.

Do not invent parallel APIs when existing APIs can be reused.

Do not break existing vocabulary functionality.

# Testing

Add appropriate tests using the project's existing test framework where practical.

At minimum validate core learning logic:

* correct answer is recognized
* incorrect answer enters correction mode
* correct airplane becomes the correction target
* player cannot advance until selecting the correct airplane after a mistake
* incorrectly answered words receive higher repetition priority
* distractor set includes exactly one correct answer
* session can complete
* mastery update uses existing application logic correctly

Also manually verify:

* desktop click interaction
* tablet/touch interaction
* resizing
* long English words remain readable
* long Chinese definitions do not break layout

# First implementation priority

Prioritize a functioning learning loop over visual polish.

The first completed version should let me:

1. Open the existing website
2. Enter a new "Word Shooter" panel
3. Select or receive 5–10 vocabulary words from existing data
4. Learn several unfamiliar words in a Discover phase
5. See a Chinese meaning
6. Shoot/tap one of several English-word airplanes
7. Receive bonus ammo for correct answers
8. On a wrong answer, see the correct airplane enlarge and display the correct English + Chinese pair
9. Shoot the corrected airplane to continue
10. Encounter missed words again later
11. Finish the session
12. See results
13. Have the existing vocabulary mastery/familiarity system updated appropriately

Once this MVP is working, stop and summarize:

* files changed
* architecture used
* how the game chooses/repeats words
* how mastery is updated
* how to run/test it
* any assumptions you had to make about the existing vocabulary data model

Do not add unrelated features beyond this MVP.


