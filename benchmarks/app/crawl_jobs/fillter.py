BLACKLIST_SITEMAP = [
    r'\.(jpg|jpeg|png|gif|bmp|webp|svg|ico|tiff|tif)$',
    r'\.(mp4|avi|mov|wmv|flv|webm|mkv|m4v|3gp|mpg|mpeg)$',
    r'\.(mp3|wav|flac|aac|ogg|wma|m4a)$',
    r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt)$',
    r'\.(zip|rar|7z|tar|gz|bz2)$',
    r'\.(json|csv|xml|yaml|yml|sql)$',
    r'\.(css|js|woff|woff2|ttf|eot|otf)$',
]

URL_HTTP_BLACKLIST = [
    r'\.(jpg|jpeg|png|gif|bmp|webp|svg|ico|pdf|doc|docx|xls|xlsx|ppt|pptx|txt|zip|rar|css|js|json|xml|mp4|avi|mov|mp3|wav)$',
    r'/wp-content/', r'/assets/', r'/static/', r'/media/',
    r'/css/', r'/js/', r'/images/', r'/img/', r'/api/', r'/ajax/',
    r'/rss', r'/feed', r'/sitemap\.xml',
    r'/admin', r'/login', r'/logout', r'/privacy', r'/terms',
    r'/cookies', r'/404', r'/error',
    r'/blog/', r'/news-post/', r'/news/', r'/support\.',r'/news/',
    r'/videos/', r'/podcasts/', r'/stories/', r'/event/', r'/about/',
    r'blog?', r'/client-reviews/', r'/stories/', r'/sitemap', r'/about/',
    r'blog?',  r'/api[-_]\w+/',
    r'/post/',  r'/api[-_]\w+/',
    r'/marketplace/',  r'/templates/',
    r'/resources/',  r'/explore/',
    r'/app-market/',  r'/explore/',

]

URL_HTTP_BLACKLIST_2 = [
    # Файли
    r'\.(jpg|jpeg|png|gif|bmp|webp|svg|ico|pdf|doc|docx|xls|xlsx|ppt|pptx|txt|zip|rar|css|js|json|xml|mp4|avi|mov|mp3|wav)$',

    # Технічні шляхи
    r'/wp-content/',
    r'/content/',
    r'/experts/',
    r'/assets/',
    r'/static/',
    r'/page/',
    r'/media/',
    r'/css/',
    r'/js/',
    r'/images/',
    r'/img/',
    r'/api/',
    r'/ajax/',
    r'/rss',
    r'/feed',
    r'/sitemap\.xml',

    # Службові сторінки
    r'/admin',
    r'/login',
    r'/logout',
    r'/privacy',
    r'/terms',
    r'/cookies',
    r'/404',
    r'/error',
    r'/api/',
    r'/v1/',
    r'/api[-_]\w+/',
    r'/seo/',
    r'/post/',
    r'/app-market/',

    r'/2009/',
    r'/2010/',
    r'/2011/',
    r'/2012/',
    r'/2013/',
    r'/2014/',
    r'/2015/',
    r'/2016/',
    r'/2017/',
    r'/2018/',
    r'/2019/',
    r'/2020/',
    r'/2021/',
    r'/2022/',
    r'/2023/',

    # Блоги та новини (зазвичай не містять прямих вакансій)
    r'/blog/',
    r'/news-post/',
    r'/news/',
    r'/newsroom/',
    r'/career-story/',
    r'/support\.',
    r'/videos/',
    r'/podcasts/',
    r'/stories/',
    r'/event/',
    r'/about/',
    r'/articles/',
    r'/users/',
    r'/sdk/',
    r'/docs/',
    r'/hiring-faqs/',

    # ДОДАТКОВІ для метадата фільтрації
    r'/contact',
    r'/faq',
    r'/help',
    r'/support/',
    r'/downloads/',
    r'/gallery/',
    r'/portfolio/',
    r'/testimonials/',
    r'/reviews/',
    r'/services/',
    r'/products/',
    r'/pricing/',
    r'/plans/',
    r'/demo/',
    r'/trial/',
    r'/signup',
    r'/register',
    r'/subscribe',
    r'/newsletter',

    r'/tags/',
    r'/archive/',
    r'/sitemap',
    r'/robots\.txt',
    r'/manifest\.json',
    r'\.php\?',  # динамічні PHP сторінки з параметрами
    r'/redirect',
    r'/goto',
    r'/link/',
    r'/url/',
    r'/external/',
    r'/partners/',
    r'/affiliates/',
    r'/clients/',
    r'/case-studies/',
    r'/locations/',
    r'/tag/',
    r'/application/?$',

    # Дурна проблема — це патерн пагінації фільтрів, але на сайті MoonActive це вакансія.
    r'\?(?!(uid|vacancyId)=)[A-Za-z0-9_]+=[^&]+',
    r'/vacancies/?$',
    r'/career/?$',
    r'/careers/?$',
    r'/culture/?$',
    r'/company/?$',
    r'/join-us/?$',
    r'/dream-vacancy/?$',

    # Investor Relations та фінансові сторінки
    r'/investors?/',
    r'/investor-relations',
    r'/analyst-coverage',
    r'/financial-results',
    r'/annual-reports',
    r'/quarterly-results',
    r'/shareholder',
    r'investors?\.',  # субдомени типу investors.domain.com
    r'ir\.',  # субдомени типу ir.domain.com

    # https://plantin.peopleforce.io/careers/v/160789-ux-writer/a/new - /a/new відгукнутися не потрібно
    r'/a/new$',

]

whitelist_patterns = [
    # Прямі вказівки на вакансії
    r'\bjobs?\b',  # jobs, job (окреме слово)
    r'\bcareers?\b',  # careers, career (окреме слово)
    r'\bvacancy\b',
    r'\bvacancies\b',
    r'\bpositions?\b',
    # Складені терміни
    r'jobs?[-_]',  # jobs-our, jobs_page, тощо
    r'job?[-_]',  # job-our, job_page, тощо
    r'careers?[-_]',  # careers-page, тощо
    r'work[-_]with',  # work-with-us
    r'join[-_]us',  # join-us
    r'join[-_]team',  # join-team
    # r'/about[-_]?us/?$',  # /about-us або /about_us в кінці URL
    # r'/team/?$',  # /team в кінці URL бля фігня
    # r'/team/',  # /team в кінці URL
    r'/company/?$',  # /company в кінці URL
    r'/culture/?$',  # /culture в кінці URL
    r'/position/',
    r'/intellectsoft/', # Бред чисто щоб ловити 1 сайт
    r'work\.ua/jobs/',
    r'work\.ua/ru/jobs/',
    r'work\.ua/en/jobs/',
    # jobs.dou.ua паттерни
    r'jobs\.dou\.ua/companies/.+/vacancies/',
    r'jobs\.dou\.ua/vacancies/',
    # robota.ua паттерни
    r'robota\.ua/company\d+/vacancy\d+',
    r'robota\.ua/ua/work/',
    # hh.ua паттерни (HeadHunter)
    r'hh\.ua/vacancy/',
    r'grc\.ua/vacancy/',
    # djinni.co паттерни
    r'djinni\.co/jobs/',
    r'af.breezy.hr/p/[^/]+/?$',
    # LinkedIn паттерни
    r'linkedin\.com/jobs/view/',
    r'ordinary-thunder-6ed\.notion\.site/',
]


# ТИП 2: Дозволені домени для кроулінгу (можна заходити і парсити)
# На ці домени можна переходити і робити рекурсивний парсинг
ALLOWED_CRAWLING_DOMAINS = [
    # Ashby HQ - система HR для компаній
    'jobs.ashbyhq.com',

    'jobs.evoplay.com.ua',


    # Workable - популярна HR платформа
    'apply.workable.com',

    # Greenhouse - HR платформа
    'boards.greenhouse.io',

    # Lever - HR система
    'jobs.lever.co',

    # BambooHR
    'hiring.bamboohr.com',

    # SmartRecruiters
    r'jobs\.smartrecruiters\.com/[^/]+/\d+-'

    # JazzHR
    'apply.jazzhr.com',

    # Інші популярні ATS (Applicant Tracking Systems)
    "cleverstaff.net/",
    "peopleforce.io/careers/",
    "hurma.work/",
    "www.zoho.com/",
    "www.teamtailor.com/",
    "www.lever.co/",
    "www.greenhouse.com/",
    "www.odoo.com/",
    "breezy.hr/",
    "clickup.com/",
    "recruitee.com/",
    "jazzhr.com/",
    "signalhire.com/",
    "bamboohr.com/",
    "ashbyhq.com/",
    "loxo.co/",
    "talentlyft.com/",
    "manatal.com/",
    "workday.com/",
    "sap.com/",
    "smartrecruiters.com/",
    "oracle.com/",
    "icims.com/",
    "bullhorn.com/",
    "jobvite.com/",
    "applicantstack.com/",
    "freshworks.com/",
    "clearcompany.com/",
    "jobscore.com/",
    "pinpointhq.com/",
    "comeet.com/",
    "homerun.co/",
    "personio.com/",
    "recooty.com/",
    "trakstar.com/",
    "ukg.com/",
    "ceridian.com/",
    "adp.com/",
    "ibm.com/",
    "silkroad.com/",
    "cornerstoneondemand.com/",
    "pageuppeople.com/",
    "talentreef.com/",
    "ology.com/",
    "newtonsoftware.com/",
    "catsone.com/",
    "pcrecruiter.net/",
    "recruiterbox.com/",
    "gohire.io/",
    "workable.com/",
    "avature.net/",
    "eightfold.ai/",
    "phenom.com/",
    "beamery.com/",
    "yello.co/",
    "symphonytalent.com/",
    "paradox.ai/",
    "gr8people.com/",
    "mystaffingpro.com/",
    "recruitbpm.com/",
    "talentnest.com/",
    "ziprecruiter.com/",
    "recruitwithatlas.com/",
    "www.vincere.io/",
    "jobadder.com/",
    "recruitcrm.io/",
    "recruiterflow.com/",
    "ezekia.com/",
    "clockworkrecruiting.com/",
    "firefishsoftware.com/",
    "ordinary-thunder-6ed.notion.site/"
]



# ----------------------------------------------------
# ТИП 1: URL паттерни для розпізнавання вакансій (БЕЗ кроулінгу)
# Якщо посилання співпадає з одним із цих regex-паттернів,
# воно одразу вважається валідною вакансією, але далі не йдемо.
# ----------------------------------------------------
EXTERNAL_VACANCY_PATTERNS = [
    # work.ua паттерни
    r'work\.ua/jobs/',
    r'work\.ua/ru/jobs/',
    r'work\.ua/en/jobs/',


    # jobs.dou.ua паттерни
    r'jobs\.dou\.ua/companies/.+/vacancies/',
    r'jobs\.dou\.ua/vacancies/',

    r'jobs\.ashbyhq\.com/welltech/',

    # robota.ua паттерни
    r'robota\.ua/company\d+/vacancy\d+',

    r'jobs\.evoplay\.com.ua/careers/',

    r'jobs\.ashbyhq\.com/holywater/',

    r'universegroup\.recruitee\.com/o/',

    r'robota\.ua/ua/work/',

    # hh.ua паттерни (HeadHunter)
    r'hh\.ua/vacancy/',
    r'grc\.ua/vacancy/',

    # djinni.co паттерни
    r'djinni\.co/jobs/',

    # LinkedIn паттерни
    r'linkedin\.com/jobs/view/',

    r'careers\.epam\.com/',
    r'job\.privatbank\.ua/',

    r'jobs\.smartrecruiters\.com/[^/]+/\d+-'
]


