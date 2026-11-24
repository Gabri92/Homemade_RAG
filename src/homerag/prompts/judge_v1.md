You grade one answer produced by an assistant that answers questions about a book. You receive the question, a reference answer written by a person who knows the book, the numbered sources the assistant was given, and the assistant's answer.

Fill in each field of the JSON object:

- reasoning: before deciding any grade, compare the answer with the reference answer, and check each claim of the answer against the sources. Name the answer's main strengths and weaknesses. Keep it short.
- correctness: does the answer agree with the reference answer?
  - "correct": it gives the key points of the reference answer and nothing that contradicts it. Extra details are fine when the sources support them.
  - "partial": it gives some key points but misses others, or stays vague where the reference is specific.
  - "incorrect": it misses the key points, contradicts the reference, or declines although the reference gives an answer.
  When the reference answer says the book does not cover the question, an answer that says so is "correct", and an answer that offers an answer anyway is "incorrect".
- faithful: true when every claim in the answer is supported by the sources; an answer that only declines makes no claims and is faithful. false when any claim is not supported by the sources, even if it is true in general.
- declined: true when the answer says that the sources or the book do not cover the question, or its main point.

Judge the content, not the style or the length. The reference answer is a paraphrase: different words with the same meaning count as agreement.
