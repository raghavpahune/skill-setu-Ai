"""Demo/fallback LLM provider — rule-based responses when no API key is configured or offline."""
from ai.provider import LLMProvider


class DemoProvider(LLMProvider):
    """Rule-based fallback provider for demo mode and offline failover."""

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        ctx = context or {}
        prompt_lower = prompt.lower()

        # 1. Handle unindexed / insufficient skill queries (e.g. Go/Golang, Rust, Ruby)
        if ctx.get("data_available_for_skill") is False or (
            ctx.get("queried_skill") and not ctx["queried_skill"].get("found_in_dataset")
        ):
            tech_name = ctx.get("queried_skill", {}).get("name", "the requested technology")
            return (
                f"### Data Availability Notice: {tech_name}\n\n"
                f"The current SkillSetu Maharashtra dataset does not contain sufficient **{tech_name}**-specific job records or accredited curriculum mappings to provide verified state-level demand metrics.\n\n"
                f"#### Verified Dataset Status:\n"
                f"* **State Job Postings Tracked:** **0** verified {tech_name} job postings in the current 10-district Maharashtra index.\n"
                f"* **Curriculum Coverage:** No state-accredited ITI, polytechnic, or MSBTE vocational course currently lists {tech_name} as a standalone core competency.\n"
                f"* **State Deficit Status:** Cannot compute a verified demand percentage or deficit gap for {tech_name} due to lack of local job telemetry.\n\n"
                f"#### General Industry Context:\n"
                f"**{tech_name}** is recognized in modern software engineering for high-concurrency microservices, cloud-native backend infrastructure, and systems tooling. Related programming and cloud competencies with active verified employer demand in Maharashtra include **Python** (26% demand, 146 active roles), **Java**, **React**, and **Cloud Computing (AWS/Kubernetes)**.\n\n"
                f"#### Recommendation:\n"
                f"To track {tech_name} demand systematically, submit candidate skill feedback via the Employer Dashboard or configure specialized tech job ingestion feeds."
            )

        # 2. Handle Context-Aware Student Skill Recommendation Query (Phase 18 / Ask Copilot handoff)
        if ctx.get("queried_skill") and (
            ctx.get("student_recommendation_context")
            or ctx.get("recommendation_handoff")
            or ctx.get("query_type") == "skill_recommendation"
            or any(w in prompt_lower for w in ("target role", "target career", "why learn", "why should i learn", "skillsetu profile", "my profile", "recommendation"))
        ):
            s = ctx["queried_skill"]
            srec = ctx.get("student_recommendation_context") or {}
            handoff = ctx.get("recommendation_handoff") or {}

            cand_name_raw = srec.get("candidate_name") or handoff.get("student_name")
            cand_name = str(cand_name_raw) if cand_name_raw else "Candidate"
            target_role_raw = srec.get("target_career_goal") or srec.get("top_recommended_role") or handoff.get("target_role")
            target_role = str(target_role_raw) if target_role_raw else "Target Career"
            sname = str(s.get("name") or "This Competency")
            category = s.get("category", "Technical Specialization")
            nsqf = s.get("nsqf_level") or 7
            demand_pct = s.get("demand_pct", 0)
            demand_count = s.get("demand_count", 0)
            total_jobs = s.get("total_jobs_tracked", 0)
            gap_pct = s.get("gap_pct", 0)
            priority = s.get("priority", "HIGH")
            dist_map = s.get("district_distribution", {})
            dist_str = ", ".join([f"**{d}** ({c} jobs)" for d, c in dist_map.items()]) if dist_map else "**Pune**, **Mumbai**, and **Nagpur** industrial clusters"

            # Missing prerequisites & candidate alignment
            missing_skills = srec.get("missing_skills") or handoff.get("missing_prerequisites") or []
            matching_skills = srec.get("matching_skills", [])
            readiness_score = srec.get("readiness_score", 0)

            has_srec = bool(ctx.get("student_recommendation_context"))
            has_explicit_missing = bool(
                (has_srec and (srec.get("is_queried_skill_missing") or any(sname.lower() == str(m).lower() for m in missing_skills)))
                or (not has_srec and any(sname.lower() == str(m).lower() for m in (handoff.get("missing_prerequisites") or [])))
            )
            has_explicit_acquired = bool(
                has_srec and (srec.get("is_queried_skill_acquired") or any(sname.lower() == str(m).lower() for m in matching_skills))
            )

            if has_explicit_acquired:
                status_badge = "✓ Acquired Competency"
            elif has_explicit_missing:
                status_badge = "⚠️ Missing Prerequisite"
            else:
                status_badge = "Not assessed"

            prereq_list = [str(m) for m in missing_skills if str(m).lower() != sname.lower()]
            prereqs_str = ", ".join(prereq_list) if prereq_list else ("Fundamental technical baseline in place" if has_srec else "Not assessed")

            # Relevant courses from dataset
            raw_courses = s.get("sample_courses") or handoff.get("relevant_courses") or []
            sample_courses = [c for c in raw_courses if isinstance(c, dict)]
            if sample_courses:
                courses_md = "\n".join([
                    f"* **{c.get('name', 'Course')}** — {c.get('institute', 'State Technical Institute')}" + (f" ({c.get('district')})" if c.get('district') else "")
                    for c in sample_courses
                ])
            else:
                courses_md = f"* *No accredited SkillSetu course currently teaching '{sname}' was found in the Maharashtra curriculum index.*"

            if target_role.lower() == "ai engineer":
                domain_rationale = (
                    f"**{sname}** is the foundational driver for autonomous intelligence pipelines, "
                    f"contextual reasoning agents, and enterprise workflow automation. For an **{target_role}**, "
                    f"mastery of {sname} bridges high-level algorithms into industrial production systems."
                )
                tools_str = "LangChain, LlamaIndex, Vector Databases (Chroma / PGVector), Hugging Face"
                project_str = "Build an end-to-end Enterprise RAG Intelligence Pipeline for Maharashtra Labour Data"
            elif "data" in target_role.lower():
                domain_rationale = (
                    f"**{sname}** enables deep exploratory data analysis, predictive statistical modelling, "
                    f"and automated feature extraction directly feeding your **{target_role}** pipeline."
                )
                tools_str = "Pandas, NumPy, Scikit-Learn, Power BI / Tableau"
                project_str = "Construct a Real-time Labour Demand Forecasting Dashboard"
            elif "cloud" in target_role.lower():
                domain_rationale = (
                    f"**{sname}** underpins resilient, scalable cloud architectures and zero-downtime microservices "
                    f"vital for a modern **{target_role}**."
                )
                tools_str = "Docker, Kubernetes, AWS/Azure CLI, Terraform, GitHub Actions"
                project_str = "Deploy an Autoscaling Multi-Region Container Cluster on Cloud Infrastructure"
            else:
                domain_rationale = (
                    f"**{sname}** is an essential technical competency required to meet verified employer hiring "
                    f"specifications for **{target_role}**."
                )
                tools_str = f"Industry standard developer tooling for {sname}"
                project_str = f"Develop a production-grade capstone project demonstrating {sname} application"

            return (
                f"### Career Recommendation Intelligence: Why Learn {sname}?\n\n"
                f"Personalized briefing for **{cand_name}** targeting **{target_role}** based on verified Maharashtra labour intelligence:\n\n"
                f"#### 🎯 A. Why This Skill Matters\n"
                f"{domain_rationale}\n\n"
                f"#### 📊 B. Current Maharashtra Labour-Market Demand & Signals\n"
                f"* **Statewide Hiring Demand:** Appears in **{demand_pct}%** of tracked job postings (**{demand_count}** active openings across Maharashtra).\n"
                f"* **Curriculum Deficit Gap:** **{gap_pct}%** talent deficit across regional training institutes ({priority} Priority Deficit).\n"
                f"* **Key Hiring Clusters:** {dist_str}.\n"
                f"* **Target Role Benchmark:** Essential competency for **{target_role}** (NSQF Level {nsqf}).\n\n"
                f"#### 👤 C. Student Alignment & Missing Prerequisites\n"
                f"* **Target Career Goal:** **{target_role}**\n"
                f"* **Candidate Competency Status:** **{status_badge}** for {sname}.\n"
                f"* **Current Readiness Score:** **{readiness_score}%** for {target_role}.\n"
                f"* **Missing Prerequisites / Gaps to Bridge:** {prereqs_str}.\n\n"
                f"#### 🏫 D. Relevant Accredited SkillSetu Courses & Training\n"
                f"{courses_md}\n\n"
                f"#### 🚀 E. Practical Step-by-Step Learning Path\n"
                f"1. **Prerequisites Baseline:** Core foundations ({prereqs_str})\n"
                f"2. **Core Concepts:** Foundational principles and underlying architecture of {sname}\n"
                f"3. **Industry Tooling:** Hands-on application using {tools_str}\n"
                f"4. **Practical Capstone Project:** {project_str}\n"
                f"5. **Advanced Competency:** Performance tuning, security, and enterprise deployment\n"
                f"6. **Credential / NSQF Alignment:** NSQF Level {nsqf} state-recognized assessment\n"
                f"7. **Target Employment Role:** Onboarding into active **{target_role}** vacancies\n\n"
                f"#### ⚡ F. Concrete Next Action\n"
                f"Review accredited training modules listed above or initiate your modular learning roadmap in the Student Dashboard to bridge your {gap_pct}% deficit gap."
            )

        # 2b. Handle verified indexed skill queries (general overview)
        if ctx.get("data_available_for_skill") is True and ctx.get("queried_skill"):
            s = ctx["queried_skill"]
            dist_map = s.get("district_distribution", {})
            dist_str = ", ".join([f"**{d}** ({c} jobs)" for d, c in dist_map.items()]) if dist_map else "Statewide distribution across industrial clusters"
            
            sample_courses = s.get("sample_courses", [])
            if sample_courses:
                courses_str = "\n".join([f"* **{c['name']}** ({c.get('institute', 'State Technical Institute')})" for c in sample_courses])
            else:
                courses_str = "* Vocational curriculum modules currently integrated across state ITIs and polytechnics."

            return (
                f"### Verified Skill Intelligence: {s['name']}\n\n"
                f"Based on indexed SkillSetu labour-market records across Maharashtra:\n\n"
                f"* **Category / Domain:** {s.get('category', 'Technical')} (NSQF Level {s.get('nsqf_level', 'N/A')})\n"
                f"* **Active Hiring Demand:** Appears in **{s.get('demand_pct', 0)}%** of tracked job postings (**{s.get('demand_count', 0)}** active postings out of {s.get('total_jobs_tracked', 0)} total).\n"
                f"* **Curriculum Coverage:** Estimated at **{s.get('coverage_pct', 0)}%** across accredited state training programs.\n"
                f"* **Labour Deficit Gap:** **{s.get('gap_pct', 0)}%** ({s.get('priority', 'MEDIUM')} Priority Deficit).\n\n"
                f"#### Regional Distribution:\n"
                f"{dist_str}\n\n"
                f"#### Accredited Training Modules:\n"
                f"{courses_str}\n\n"
                f"#### Recommended Action:\n"
                f"Expand industry-aligned practical training in **{s['name']}** at regional technical institutions to bridge the {s.get('gap_pct', 0)}% curriculum deficit."
            )

        # 2b. Phase 17: Grounded Student Career Recommendation Intelligence
        if ctx.get("student_recommendation_context"):
            srec = ctx["student_recommendation_context"]
            cand_name = srec.get("candidate_name", "Candidate")
            top_role = srec.get("top_recommended_role", "Target Role")
            match_pct = srec.get("top_role_match_pct", 0)
            readiness_score = srec.get("readiness_score", 0)
            readiness_hl = srec.get("readiness_headline", "Candidate Assessment")
            openings = srec.get("validated_openings_count", 0)
            matching = ", ".join(srec.get("matching_skills", [])) or "None identified"
            missing = ", ".join(srec.get("missing_skills", [])) or "None (Fully acquired)"
            reasons_md = "\n".join([f"* **{r}**" for r in srec.get("explanation_reasons", [])]) or "* Grounded in verified SkillSetu labour benchmarks."

            roadmap_md = "\n".join([
                f"* **Step {st['step']}:** Master **{st['skill']}** — {st['why']}"
                for st in srec.get("personalized_roadmap", [])
            ]) or "* Build an industrial capstone portfolio to validate competencies."

            emp_signals_md = "\n".join([
                f"* **{e['company_name']}** ({e.get('district', 'Maharashtra')}): {e['job_role']} — **{e.get('openings_count', 1)} Openings** (Status: {e.get('validation_status', 'VALIDATED')})"
                for e in srec.get("validated_employer_signals", [])
            ]) or "* General verified vocational hiring demand across state corridors."

            gov_ops_md = "\n".join([
                f"* **{g['name']}** ({g.get('department', 'Govt of Maharashtra')}): {g.get('opportunity_type', 'training')}"
                for g in srec.get("matched_government_opportunities", [])
            ]) or "* State welfare fee concessions and MahaDBT vocational stipends apply."

            return (
                f"### Career Recommendation Briefing for {cand_name}\n\n"
                f"Here is your personalized, grounded career intelligence summary based on your self-reported competencies and verified Maharashtra labour demand:\n\n"
                f"#### 🎯 Recommended Pathway: **{top_role}**\n"
                f"* **Competency Match Score:** **{match_pct}%**\n"
                f"* **Overall Readiness:** **{readiness_score}%** ({readiness_hl})\n"
                f"* **Matching Skills ({len(srec.get('matching_skills', []))}):** {matching}\n"
                f"* **Targeted Skill Gaps ({len(srec.get('missing_skills', []))}):** {missing}\n\n"
                f"#### 💡 Why This Role is Recommended:\n"
                f"{reasons_md}\n\n"
                f"#### 🏢 Validated Employer Demand ({openings} Openings):\n"
                f"{emp_signals_md}\n\n"
                f"#### 🏛️ Matched Government Schemes & Opportunities:\n"
                f"{gov_ops_md}\n\n"
                f"#### 🚀 Step-by-Step Learning Roadmap:\n"
                f"{roadmap_md}\n\n"
                f"> **Provenance Note:** All metrics are deterministically computed from your assessment, strictly validated employer requirements, and government datasets. No ungrounded claims are made."
            )


        # 3. District-specific queries (when no specific unindexed skill is queried)
        if ctx.get("focused_district"):
            fd = ctx["focused_district"]
            dname = fd.get("district", "Maharashtra District")
            roles_list = [r.get("role", str(r)) if isinstance(r, dict) else str(r) for r in fd.get("top_roles", [])[:5]]
            skills_list = [s.get("skill_name", str(s)) if isinstance(s, dict) else str(s) for s in fd.get("top_skills", [])[:5]]
            ind_list = [f"{i.get('industry', str(i))} ({i.get('count', 0)} jobs)" if isinstance(i, dict) else str(i) for i in fd.get("industry_demand", [])[:4]]
            gaps_list = fd.get("skill_gaps", [])[:4]
            courses_list = fd.get("local_courses", [])[:4]

            roles_str = ", ".join(roles_list) if roles_list else "Data unavailable in current index"
            skills_str = ", ".join(skills_list) if skills_list else "Data unavailable in current index"
            ind_str = ", ".join(ind_list) if ind_list else "General Industrial & Services"

            # Skill Gaps Table / Summary
            if gaps_list:
                gaps_md = "\n".join([
                    f"* **{g.get('skill_name', 'Skill')}:** {g.get('gap_pct', 0)}% deficit ({g.get('priority', 'MEDIUM')} Priority • {g.get('demand_count', 0)} job requirements)"
                    for g in gaps_list
                ])
            else:
                gaps_md = "* No severe curriculum deficits flagged; local output aligns with baseline demand."

            # Courses Summary
            if courses_list:
                courses_md = "\n".join([
                    f"* **{c.get('name', 'Course')}** at {c.get('institute', 'State Technical Institute')} (Enrolment: {c.get('enrolment', 0)}, Placement Rate: {c.get('placement_rate', 0)}%)"
                    for c in courses_list
                ])
            else:
                courses_md = "* Registered vocational courses and ITI programs across district."

            total_jobs = fd.get('total_jobs', 0)
            total_courses = fd.get('total_courses', 0)
            total_enrolment = fd.get('total_enrolment', 0)

            jobs_display = f"**{total_jobs}** verified postings" if total_jobs > 0 else "0 active postings tracked (Data unavailable in current index)"
            courses_display = f"**{total_courses}** registered courses (**{total_enrolment}** annual seats)" if total_courses > 0 else "Data unavailable in current index"

            return (
                f"### {dname} District Workforce Intelligence Briefing\n\n"
                f"Here is the current SkillSetu intelligence briefing for **{dname}**, grounded in verified state labour-market records:\n\n"
                f"#### 1. Labour & Industrial Demand:\n"
                f"* **Active Job Openings:** {jobs_display}.\n"
                f"* **Primary Industry Clusters:** {ind_str}.\n"
                f"* **Top In-Demand Roles:** {roles_str}.\n"
                f"* **Core Required Competencies:** {skills_str}.\n\n"
                f"#### 2. Critical Skill Deficits & Gaps:\n"
                f"{gaps_md}\n\n"
                f"#### 3. Institutional Training Capacity:\n"
                f"* **Accredited Training Infrastructure:** {courses_display}.\n"
                f"{courses_md}\n\n"
                f"#### 4. Recommended Policy Interventions:\n"
                f"1. **Expand ITI Quotas:** Increase intake in high-deficit trades across {dname} technical institutes.\n"
                f"2. **Industry Apprenticeships:** Link local manufacturing units with NAPS apprenticeship stipends.\n"
                f"3. **Modernize Syllabi:** Refresh legacy modules with modern hands-on automation and technical standards."
            )

        # 4. Gaps / Deficit query
        if "gap" in prompt_lower or "deficit" in prompt_lower:
            return (
                "### Identified Skill Deficit Analysis\n\n"
                "Comparison of employer job specifications against accredited vocational curricula in Maharashtra:\n\n"
                "| Skill Name | Domain | Priority | Demand % | Coverage % | Deficit |\n"
                "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                "| **Python** | Programming | **HIGH** | 26% | 18% | **8%** |\n"
                "| **PLC Programming** | Manufacturing | **HIGH** | 14% | 6% | **8%** |\n"
                "| **IoT** | Emerging Tech | **MEDIUM** | 10% | 3% | **7%** |\n"
                "| **Robotics** | Automation | **MEDIUM** | 9% | 2% | **7%** |\n\n"
                "> **Note:** Deficits represent unmet hiring demand across Maharashtra industrial clusters (Pune, Mumbai, Nagpur)."
            )

        # 5. Curriculum query
        if "curriculum" in prompt_lower or "syllabus" in prompt_lower:
            return (
                "### Curriculum Alignment Recommendations\n\n"
                "1. **Add AI Agents & RAG modules** to Computer Engineering & IT curricula (projected +24% hiring surge).\n"
                "2. **Introduce EV Battery Management Systems (BMS)** in automotive trade syllabi.\n"
                "3. **Audit Low-Placement Courses:** Flag courses with under 50% placement for vocational syllabus refresh."
            )

        # 6. Career roadmap query
        if "career" in prompt_lower or "roadmap" in prompt_lower:
            return (
                "### Recommended Technical Career Roadmap\n\n"
                "1. **Stage 1 (Core Foundations):** Core Programming / Engineering Principles + Applied Mathematics.\n"
                "2. **Stage 2 (Specialization):** Domain Frameworks, Hands-on Tooling, and Practical Projects.\n"
                "3. **Stage 3 (Advanced Systems):** Cloud Infrastructure, Distributed Architectures, and Automated Testing.\n"
                "4. **Stage 4 (Industry Placement):** Production Internship / NAPS Apprenticeship Capstone."
            )

        # 7. Employer feedback query
        if "employer" in prompt_lower or "validation" in prompt_lower:
            return (
                "### Employer Validation & Bottleneck Intelligence\n\n"
                "* **Validated Hiring Signals:** 15 active employer demand signals verified across Maharashtra.\n"
                "* **Primary Bottlenecks:** Experienced PLC Programmers, EV Powertrain Technicians, and AI System Engineers.\n"
                "* **Action:** Submit candidate skill feedback to accelerate state-level syllabus adjustments."
            )

        if "forecast" in prompt_lower or "trend" in prompt_lower:
            return (
                "### 12-to-24 Month Skill Forecast\n\n"
                "* **Rising Exponentially:** AI Agents (+45%), Generative AI (+42%), EV Battery Tech (+38%).\n"
                "* **Stable Core:** Python, React, Cloud Computing, CNC Machining.\n"
                "* **Automating / Shifting:** Traditional Manual Drafting, Basic Data Entry."
            )

        if "transition" in prompt_lower or "upskill" in prompt_lower or "employee" in prompt_lower or "mobility" in prompt_lower or ctx.get("employee_profile"):
            ep = ctx.get("employee_profile") or {}
            c_role = ep.get("current_role") or "Experienced Professional"
            t_role = ep.get("target_role") or "Emerging Technology Lead"
            skills_list = ep.get("skills") or ["Technical Foundations", "Domain Experience"]
            skills_str = ", ".join(f"**{s}**" for s in skills_list[:5])
            certs = ep.get("certifications") or []
            certs_str = ", ".join(certs) if certs else "State / Industry Recognized Credentials"
            return (
                f"### Career Transition & Upskilling Intelligence\n\n"
                f"Strategic career transition path from **{c_role}** to **{t_role}** based on active Maharashtra industrial demands:\n\n"
                f"#### 1. Transferable Competencies:\n"
                f"* **Current Baseline:** {skills_str}\n"
                f"* **Verified Credentials:** {certs_str}\n\n"
                f"#### 2. Strategic Upskilling Bridge:\n"
                f"1. **Audit High-Demand Frameworks:** Align existing competencies with state growth sectors (Smart Manufacturing, Electric Vehicles, Cloud/AI).\n"
                f"2. **Hands-On Capstone:** Complete an industry-aligned technical prototype demonstrating bridge competencies.\n"
                f"3. **Targeted Certification:** Attain NSQF Level 6/7 specialized certifications recognized by Maharashtra industrial clusters (Pune, Chhatrapati Sambhajinagar, Mumbai)."
            )

        return (
            "### SkillSetu Labour-Market Intelligence\n\n"
            "SkillSetu continuously indexes 55+ skills, 560+ job postings, and 27 accredited training courses across 10 Maharashtra districts.\n\n"
            "**Suggested inquiries:**\n"
            "* *'Tell me about requirement for Python developer'*\n"
            "* *'What are the biggest skill gaps in Pune?'*\n"
            "* *'What is the demand for Go developer?'*\n"
            "* *'Which vocational courses show high placement rates?'*"
        )
