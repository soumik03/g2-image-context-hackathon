# **Problem Statement 2: Enrichment of Image Generation Using Structured Context**

**Theme:** Multimodal AI: Images  
**Problem Statement Name:** Enrichment of image generation using structured context  
---

**Overview**  
Consider an image generation pipeline which depends on structured context to refine the outputs. How would you guarantee that generation quality is achieved in the generation process?  
**Note:** This exercise requires an API key for accessing Gemini models. You can request a free API key for yourself at [https://aistudio.google.com/](https://aistudio.google.com/).  
---

## **Tech Stack**

* Python, TypeScript, or Ruby preferred

---

## **Task**

1. **Propose Pipeline:**  
* Propose an image generation pipeline for display advertisement generation that uses Gemini 3.1 Flash-Lite Image or Gemini 3.1 Flash Image.  
* The pipeline should take a reference product image plus three structured text fields as input:  
* Target geography  
* Season  
* Freeform text that must be included in the generated image  
* This added context leads to refinement of the generated image.  
* *Note: Text rendering may not reliably be perfect; this is acceptable, but consider this in your solution.*  
2. **Strategy & Implementation:**  
* Decide an effective generation strategy for images generated using this pipeline, then implement the generation pipeline.  
* The maximum resolution of generated images must be 1K (long edge ≤ 1024px).  
3. **Evaluator Implementation:**  
* Implement an evaluator that judges the quality of the outputs across ≈20 images output from the pipeline.  
4. **Automated Testing:**  
* Demonstrate that your evaluator can identify passing and failing outputs against quality metrics you define through automated tests.  
* At a minimum, consider:  
1. Context adherence  
2. Fidelity of reference product  
3. Text rendering fidelity

---

## **Restrictions**

* **Coding Agent:** A coding agent may be used, but you must explain how you collaborated with (prompted) the agent to arrive at your solution.

---

## **Submission Format**

* **Solution Details:** Details about your solution, including an explanation of your engineering design, your rationale for it, definition of success criteria for your solution, level of achievement against your criteria, and any limitations of your solution, in a Markdown or PDF file.  
* **Disclosure of Coding Agent Use:** You must disclose the use of coding agents in developing your project. Where used, you must explain how you directed the agent to arrive at the outputs it generated (e.g., by sharing architectural requirements supplied to the agent or providing summarized traces of interactions).

**Repository:** GitHub/GitLab repository for code commit containing your solution, as well as your golden dataset and tests.

