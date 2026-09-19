from typing import List
try:
    from ..schemas import JobPosting
except (ImportError, ValueError):
    from schemas import JobPosting


DEMO_JOBS_RAW = [
    # 1-5: Python Developer Roles
    {
        "job_id": "JOB-001",
        "title": "Python Developer",
        "company": "Tata Consultancy Services",
        "location": "Pune",
        "required_skills": ["Python", "Django", "SQL", "Git", "REST API"],
        "description": "Seeking an enthusiastic Python developer to build robust enterprise web applications using Django and relational databases.",
        "job_url": "https://careers.tcs.com/jobs/JOB-001"
    },
    {
        "job_id": "JOB-002",
        "title": "Senior Python Backend Engineer",
        "company": "Infosys",
        "location": "Bengaluru",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "Microservices"],
        "description": "Lead the design and development of high-throughput asynchronous backend services using FastAPI and containerized microservices.",
        "job_url": "https://careers.infosys.com/jobs/JOB-002"
    },
    {
        "job_id": "JOB-003",
        "title": "Junior Python Developer",
        "company": "Persistent Systems",
        "location": "Nagpur",
        "required_skills": ["Python", "Flask", "MySQL", "Git", "HTML", "CSS"],
        "description": "Opportunity for fresh graduates with solid Python foundations to develop REST APIs and web interfaces.",
        "job_url": "https://careers.persistent.com/jobs/JOB-003"
    },
    {
        "job_id": "JOB-004",
        "title": "Python Automation Engineer",
        "company": "Wipro",
        "location": "Hyderabad",
        "required_skills": ["Python", "Selenium", "PyTest", "CI/CD", "Linux"],
        "description": "Develop automated test suites, script execution frameworks, and quality reporting pipelines in Python.",
        "job_url": "https://careers.wipro.com/jobs/JOB-004"
    },
    {
        "job_id": "JOB-005",
        "title": "Python Data Engineer",
        "company": "Cognizant",
        "location": "Chennai",
        "required_skills": ["Python", "Apache Spark", "SQL", "AWS", "Airflow"],
        "description": "Architect ETL pipelines and big data ingestion frameworks for global healthcare clients.",
        "job_url": "https://careers.cognizant.com/jobs/JOB-005"
    },

    # 6-10: React & Frontend Developer Roles
    {
        "job_id": "JOB-006",
        "title": "React Developer",
        "company": "Swiggy",
        "location": "Bengaluru",
        "required_skills": ["React", "JavaScript", "Redux", "HTML", "CSS", "REST API"],
        "description": "Build delightful consumer-facing web experiences using modern React hooks, state management, and responsive CSS.",
        "job_url": "https://careers.swiggy.com/jobs/JOB-006"
    },
    {
        "job_id": "JOB-007",
        "title": "Frontend Engineer (React & TypeScript)",
        "company": "Razorpay",
        "location": "Bengaluru",
        "required_skills": ["React", "TypeScript", "Next.js", "Tailwind CSS", "Jest"],
        "description": "Create scalable payment interfaces with high test coverage, strict typing, and server-side rendered pages.",
        "job_url": "https://careers.razorpay.com/jobs/JOB-007"
    },
    {
        "job_id": "JOB-008",
        "title": "React UI/UX Developer",
        "company": "Zepto",
        "location": "Mumbai",
        "required_skills": ["React", "JavaScript", "HTML5", "CSS3", "Figma", "Web Performance"],
        "description": "Translate Figma designs into pixel-perfect, hyper-optimized React components for quick commerce.",
        "job_url": "https://careers.zepto.com/jobs/JOB-008"
    },
    {
        "job_id": "JOB-009",
        "title": "Junior Frontend Developer",
        "company": "Zensar Technologies",
        "location": "Pune",
        "required_skills": ["React", "JavaScript", "Bootstrap", "Git"],
        "description": "Great starter role for web enthusiasts proficient in React components and responsive styling frameworks.",
        "job_url": "https://careers.zensar.com/jobs/JOB-009"
    },
    {
        "job_id": "JOB-010",
        "title": "Senior Frontend Architect",
        "company": "MakeMyTrip",
        "location": "Gurgaon",
        "required_skills": ["React", "JavaScript", "Micro-Frontends", "Webpack", "Performance Optimization"],
        "description": "Lead frontend architectural migrations, code-splitting strategies, and multi-brand design systems.",
        "job_url": "https://careers.makemytrip.com/jobs/JOB-010"
    },

    # 11-15: Backend Developer Roles
    {
        "job_id": "JOB-011",
        "title": "Backend Developer",
        "company": "Jio Platforms",
        "location": "Mumbai",
        "required_skills": ["Python", "FastAPI", "MongoDB", "Docker", "Kafka"],
        "description": "Scale event-driven streaming backend platforms serving hundreds of millions of telecom subscribers.",
        "job_url": "https://careers.jio.com/jobs/JOB-011"
    },
    {
        "job_id": "JOB-012",
        "title": "Golang Backend Developer",
        "company": "PhonePe",
        "location": "Bengaluru",
        "required_skills": ["Go", "Distributed Systems", "gRPC", "PostgreSQL", "Redis"],
        "description": "Engineer low-latency distributed transaction engines handling millions of daily UPI payments.",
        "job_url": "https://careers.phonepe.com/jobs/JOB-012"
    },
    {
        "job_id": "JOB-013",
        "title": "Node.js Backend Engineer",
        "company": "Freshworks",
        "location": "Chennai",
        "required_skills": ["Node.js", "Express.js", "TypeScript", "PostgreSQL", "AWS"],
        "description": "Design modular SaaS APIs and real-time webhook systems for enterprise customer support software.",
        "job_url": "https://careers.freshworks.com/jobs/JOB-013"
    },
    {
        "job_id": "JOB-014",
        "title": "Backend Systems Engineer",
        "company": "Zoho Corporation",
        "location": "Chennai",
        "required_skills": ["Java", "C++", "SQL", "Multithreading", "Networking"],
        "description": "Work on custom storage engines, in-house database clusters, and secure transport protocols.",
        "job_url": "https://careers.zoho.com/jobs/JOB-014"
    },
    {
        "job_id": "JOB-015",
        "title": "Cloud Backend Developer",
        "company": "Capgemini",
        "location": "Hyderabad",
        "required_skills": ["Python", "AWS Lambda", "API Gateway", "DynamoDB", "Serverless"],
        "description": "Implement cost-efficient serverless backend architectures for international finance clients.",
        "job_url": "https://careers.capgemini.com/jobs/JOB-015"
    },

    # 16-20: Data Analyst Roles
    {
        "job_id": "JOB-016",
        "title": "Data Analyst",
        "company": "HDFC Bank",
        "location": "Mumbai",
        "required_skills": ["SQL", "Excel", "PowerBI", "Python", "Data Visualization"],
        "description": "Extract transactional metrics, develop executive PowerBI dashboards, and analyze customer churn patterns.",
        "job_url": "https://careers.hdfcbank.com/jobs/JOB-016"
    },
    {
        "job_id": "JOB-017",
        "title": "Senior BI & Data Analyst",
        "company": "Flipkart",
        "location": "Bengaluru",
        "required_skills": ["SQL", "Tableau", "Python", "Statistics", "A/B Testing"],
        "description": "Partner with supply chain product managers to design experiments and evaluate operational KPIs.",
        "job_url": "https://careers.flipkart.com/jobs/JOB-017"
    },
    {
        "job_id": "JOB-018",
        "title": "Financial Data Analyst",
        "company": "ICICI Lombard",
        "location": "Mumbai",
        "required_skills": ["Excel", "SQL", "R", "Financial Modeling", "Statistics"],
        "description": "Conduct actuarial modeling, risk assessments, and insurance portfolio performance analysis.",
        "job_url": "https://careers.icicilombard.com/jobs/JOB-018"
    },
    {
        "job_id": "JOB-019",
        "title": "Healthcare Data Analyst",
        "company": "Apollo Hospitals",
        "location": "Hyderabad",
        "required_skills": ["SQL", "Python", "Healthcare Analytics", "PowerBI", "Excel"],
        "description": "Analyze clinical patient outcomes, hospital resource utilization, and diagnostic turnaround times.",
        "job_url": "https://careers.apollohospitals.com/jobs/JOB-019"
    },
    {
        "job_id": "JOB-020",
        "title": "Junior Business Analyst",
        "company": "Mu Sigma",
        "location": "Bengaluru",
        "required_skills": ["SQL", "Excel", "Data Cleaning", "Problem Solving", "Communication"],
        "description": "Synthesize unstructured enterprise datasets into actionable insights for Fortune 500 decision makers.",
        "job_url": "https://careers.musigma.com/jobs/JOB-020"
    },

    # 21-25: Machine Learning Intern & Entry-Level Roles
    {
        "job_id": "JOB-021",
        "title": "Machine Learning Intern",
        "company": "Tech Mahindra",
        "location": "Pune",
        "required_skills": ["Python", "NumPy", "Pandas", "Scikit-learn", "Machine Learning"],
        "description": "Six-month paid internship focusing on supervised learning models, data wrangling, and model benchmarking.",
        "job_url": "https://careers.techmahindra.com/jobs/JOB-021"
    },
    {
        "job_id": "JOB-022",
        "title": "AI/ML Research Intern",
        "company": "Tata Elxsi",
        "location": "Bengaluru",
        "required_skills": ["Python", "PyTorch", "Computer Vision", "OpenCV", "Deep Learning"],
        "description": "Assist research scientists in developing perception algorithms for autonomous driving simulators.",
        "job_url": "https://careers.tataelxsi.com/jobs/JOB-022"
    },
    {
        "job_id": "JOB-023",
        "title": "NLP Data Science Intern",
        "company": "InMobi",
        "location": "Bengaluru",
        "required_skills": ["Python", "NLP", "HuggingFace", "Transformers", "Pandas"],
        "description": "Explore transformer-based sentiment analysis and ad copy classification algorithms.",
        "job_url": "https://careers.inmobi.com/jobs/JOB-023"
    },
    {
        "job_id": "JOB-024",
        "title": "Applied ML Intern",
        "company": "Ola Electric",
        "location": "Bengaluru",
        "required_skills": ["Python", "Scikit-learn", "Time Series Analysis", "SQL", "Git"],
        "description": "Help model battery degradation parameters and vehicle telematics sensor streams.",
        "job_url": "https://careers.olaelectric.com/jobs/JOB-024"
    },
    {
        "job_id": "JOB-025",
        "title": "Data Science Trainee",
        "company": "L&T Infotech",
        "location": "Mumbai",
        "required_skills": ["Python", "Statistics", "Pandas", "NumPy", "Linear Algebra"],
        "description": "Comprehensive graduate training program covering predictive analytics, regression, and model deployment.",
        "job_url": "https://careers.lntinfotech.com/jobs/JOB-025"
    },

    # 26-30: Full Stack Developer Roles
    {
        "job_id": "JOB-026",
        "title": "Full Stack Developer",
        "company": "Paytm",
        "location": "Noida",
        "required_skills": ["React", "Node.js", "JavaScript", "MongoDB", "Docker"],
        "description": "Deliver end-to-end features for merchant payment portals using the MERN technology stack.",
        "job_url": "https://careers.paytm.com/jobs/JOB-026"
    },
    {
        "job_id": "JOB-027",
        "title": "Python Full Stack Engineer",
        "company": "CitiusTech",
        "location": "Pune",
        "required_skills": ["Python", "Django", "React", "PostgreSQL", "REST API"],
        "description": "Build HIPAA-compliant digital health applications combining Django backends with React frontend dashboards.",
        "job_url": "https://careers.citiustech.com/jobs/JOB-027"
    },
    {
        "job_id": "JOB-028",
        "title": "Full Stack Software Engineer",
        "company": "CRED",
        "location": "Bengaluru",
        "required_skills": ["React", "Node.js", "TypeScript", "PostgreSQL", "Redis", "Kafka"],
        "description": "Work on high-stakes financial reward systems requiring robust concurrency, sleek UI, and bulletproof security.",
        "job_url": "https://careers.cred.club/jobs/JOB-028"
    },
    {
        "job_id": "JOB-029",
        "title": "Java Full Stack Developer",
        "company": "CGI India",
        "location": "Hyderabad",
        "required_skills": ["Java", "Spring Boot", "Angular", "MySQL", "Docker"],
        "description": "Modernize legacy government and logistics systems into Angular micro-frontends backed by Spring Boot.",
        "job_url": "https://careers.cgi.com/jobs/JOB-029"
    },
    {
        "job_id": "JOB-030",
        "title": "Full Stack Web Developer",
        "company": "Info Edge (Naukri.com)",
        "location": "Noida",
        "required_skills": ["JavaScript", "React", "Python", "SQL", "Git"],
        "description": "Enhance talent search engines and recruiter collaboration tools serving millions of job seekers.",
        "job_url": "https://careers.infoedge.com/jobs/JOB-030"
    },

    # 31-35: Java Developer Roles
    {
        "job_id": "JOB-031",
        "title": "Java Developer",
        "company": "Wipro",
        "location": "Hyderabad",
        "required_skills": ["Java", "Spring Boot", "Microservices", "SQL", "Git"],
        "description": "Develop resilient, horizontally scalable microservices for multinational banking institutions.",
        "job_url": "https://careers.wipro.com/jobs/JOB-031"
    },
    {
        "job_id": "JOB-032",
        "title": "Senior Java Backend Engineer",
        "company": "Oracle India",
        "location": "Bengaluru",
        "required_skills": ["Java", "Spring Boot", "Hibernate", "Oracle DB", "Docker", "Kubernetes"],
        "description": "Build high-reliability enterprise cloud services powering multi-tenant ERP suites.",
        "job_url": "https://careers.oracle.com/jobs/JOB-032"
    },
    {
        "job_id": "JOB-033",
        "title": "Java Software Engineer",
        "company": "Mindtree",
        "location": "Pune",
        "required_skills": ["Java", "REST API", "Spring Boot", "Maven", "JUnit"],
        "description": "Participate in agile sprints delivering clean code, automated unit tests, and API documentations.",
        "job_url": "https://careers.mindtree.com/jobs/JOB-033"
    },
    {
        "job_id": "JOB-034",
        "title": "Java Microservices Specialist",
        "company": "Barclays",
        "location": "Pune",
        "required_skills": ["Java", "Spring Boot", "Kafka", "AWS", "Docker"],
        "description": "Architect mission-critical payment settlement networks with sub-second SLA constraints.",
        "job_url": "https://careers.barclays.com/jobs/JOB-034"
    },
    {
        "job_id": "JOB-035",
        "title": "Junior Java Developer",
        "company": "Mphasis",
        "location": "Nagpur",
        "required_skills": ["Java", "Core Java", "SQL", "Object-Oriented Programming", "Git"],
        "description": "Solid entry-level opening for candidates well-versed in Core Java, OOP design patterns, and relational SQL.",
        "job_url": "https://careers.mphasis.com/jobs/JOB-035"
    },

    # 36-40: Software Engineer Roles
    {
        "job_id": "JOB-036",
        "title": "Software Engineer",
        "company": "Persistent Systems",
        "location": "Nagpur",
        "required_skills": ["Python", "C++", "Data Structures", "Algorithms", "Git"],
        "description": "Solve challenging computational problems, optimize core algorithms, and ship modular software modules.",
        "job_url": "https://careers.persistent.com/jobs/JOB-036"
    },
    {
        "job_id": "JOB-037",
        "title": "Associate Software Engineer",
        "company": "Accenture",
        "location": "Kolkata",
        "required_skills": ["Java", "Python", "SQL", "Software Engineering Principles", "Problem Solving"],
        "description": "Join our global innovation centers delivering end-to-end IT transformation projects.",
        "job_url": "https://careers.accenture.com/jobs/JOB-037"
    },
    {
        "job_id": "JOB-038",
        "title": "Systems Software Engineer",
        "company": "Cisco Systems",
        "location": "Bengaluru",
        "required_skills": ["C++", "Linux", "Networking Protocols", "Data Structures", "Multithreading"],
        "description": "Program next-generation enterprise routing, switching, and software-defined network switches.",
        "job_url": "https://careers.cisco.com/jobs/JOB-038"
    },
    {
        "job_id": "JOB-039",
        "title": "Software Development Engineer (SDE-1)",
        "company": "Amazon",
        "location": "Hyderabad",
        "required_skills": ["Java", "Data Structures", "Algorithms", "Object-Oriented Design", "AWS"],
        "description": "Build high-scale customer fulfillment services for global e-commerce and logistics operations.",
        "job_url": "https://careers.amazon.com/jobs/JOB-039"
    },
    {
        "job_id": "JOB-040",
        "title": "Embedded Software Engineer",
        "company": "Bosch India",
        "location": "Coimbatore",
        "required_skills": ["Embedded C", "C++", "RTOS", "Microcontrollers", "Git"],
        "description": "Develop firmware and control unit applications for connected electric vehicle subsystems.",
        "job_url": "https://careers.bosch.in/jobs/JOB-040"
    },

    # 41-45: Data Scientist Roles
    {
        "job_id": "JOB-041",
        "title": "Data Scientist",
        "company": "Fractal Analytics",
        "location": "Bengaluru",
        "required_skills": ["Python", "Machine Learning", "Deep Learning", "SQL", "Statistics"],
        "description": "Translate complex enterprise business challenges into predictive models and algorithmic solutions.",
        "job_url": "https://careers.fractal.ai/jobs/JOB-041"
    },
    {
        "job_id": "JOB-042",
        "title": "Lead Data Scientist",
        "company": "Reliance Jio",
        "location": "Mumbai",
        "required_skills": ["Python", "Machine Learning", "NLP", "Big Data", "PyTorch"],
        "description": "Drive data science strategy across conversational AI, customer telemetry, and personalization engines.",
        "job_url": "https://careers.jio.com/jobs/JOB-042"
    },
    {
        "job_id": "JOB-043",
        "title": "Senior Data Scientist",
        "company": "Tiger Analytics",
        "location": "Chennai",
        "required_skills": ["Python", "Scikit-learn", "XGBoost", "Feature Engineering", "SQL"],
        "description": "Craft bespoke analytics, customer lifetime value modeling, and pricing optimization algorithms.",
        "job_url": "https://careers.tigeranalytics.com/jobs/JOB-043"
    },
    {
        "job_id": "JOB-044",
        "title": "Data Scientist - Computer Vision",
        "company": "Krutrim SI Designs",
        "location": "Bengaluru",
        "required_skills": ["Python", "OpenCV", "PyTorch", "Deep Learning", "YOLO"],
        "description": "Train deep convolutional networks for real-time document OCR and visual inspection applications.",
        "job_url": "https://careers.krutrim.com/jobs/JOB-044"
    },
    {
        "job_id": "JOB-045",
        "title": "Healthcare Data Scientist",
        "company": "Novartis",
        "location": "Hyderabad",
        "required_skills": ["Python", "R", "Survival Analysis", "Machine Learning", "Clinical Trials"],
        "description": "Utilize real-world clinical evidence and statistical modeling to accelerate therapeutic discovery.",
        "job_url": "https://careers.novartis.com/jobs/JOB-045"
    },

    # 46-50: AI/ML Engineer Roles
    {
        "job_id": "JOB-046",
        "title": "AI/ML Engineer",
        "company": "Tata Elxsi",
        "location": "Pune",
        "required_skills": ["Python", "PyTorch", "TensorFlow", "Deep Learning", "NLP", "Docker"],
        "description": "Productionize generative AI architectures, fine-tune transformer models, and optimize inference pipelines.",
        "job_url": "https://careers.tataelxsi.com/jobs/JOB-046"
    },
    {
        "job_id": "JOB-047",
        "title": "Generative AI Engineer",
        "company": "Persistent Systems",
        "location": "Pune",
        "required_skills": ["Python", "LangChain", "LLMs", "Vector Databases", "FastAPI"],
        "description": "Build agentic workflows, RAG applications, and enterprise knowledge copilot systems.",
        "job_url": "https://careers.persistent.com/jobs/JOB-047"
    },
    {
        "job_id": "JOB-048",
        "title": "MLOps Engineer",
        "company": "Meesho",
        "location": "Bengaluru",
        "required_skills": ["Python", "Docker", "Kubernetes", "MLflow", "AWS", "CI/CD"],
        "description": "Establish automated model retraining, drift monitoring, and low-latency model serving clusters.",
        "job_url": "https://careers.meesho.com/jobs/JOB-048"
    },
    {
        "job_id": "JOB-049",
        "title": "Senior AI Engineer",
        "company": "Postman",
        "location": "Remote",
        "required_skills": ["Python", "TypeScript", "LLMs", "Prompt Engineering", "FastAPI"],
        "description": "Infuse Postman's API lifecycle platform with autonomous test generation and documentation AI capabilities.",
        "job_url": "https://careers.postman.com/jobs/JOB-049"
    },
    {
        "job_id": "JOB-050",
        "title": "NLP Engineer",
        "company": "Yellow.ai",
        "location": "Bengaluru",
        "required_skills": ["Python", "NLP", "Spacy", "Transformers", "BERT", "Docker"],
        "description": "Develop multi-lingual conversational intent classification and slot extraction pipelines for customer support bots.",
        "job_url": "https://careers.yellow.ai/jobs/JOB-050"
    }
]


def get_demo_jobs() -> List[JobPosting]:
    """
    Returns the collection of 50 demo job postings.
    Maintained separately so it can seamlessly be swapped with Jooble API data later.
    """
    return [JobPosting(**job) for job in DEMO_JOBS_RAW]
