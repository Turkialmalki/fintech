"""Sample applicant files used to populate the review workspace, and the configured requirement catalogue.

Applicant names are invented for the workspace; requirement thresholds are taken from the public
regulatory summaries in ./data (each cites its official source).
"""
from __future__ import annotations

COMPANIES = [
    {
        "key": "tamweel", "company_name_ar": "شركة دانة للدفع الآجل", "company_name_en": "Dana Pay Later Co.",
        "commercial_registration": "1010874412", "city": "الرياض", "contact_email": "compliance@danapaylater.sa",
        "website": "", "service_category": "BNPL",
        "business_model": "منصة للشراء الآن والدفع لاحقاً تقسّم المشتريات على أربع دفعات شهرية دون أي رسوم على العميل، وتتقاضى عمولة من المتاجر الشريكة.",
        "target_customers": "الأفراد المقيمون في المملكة من عمر 18 سنة فأكثر عبر شبكة من 1,200 متجر إلكتروني وفعلي.",
        "paid_up_capital_sar": 5_500_000, "expected_monthly_volume_sar": 35_000_000, "data_hosting_location": "Frankfurt, Germany",
        "uses_third_party_providers": True, "status": "SUBMITTED",
        "documents": {
            "COMMERCIAL_REGISTRATION": "السجل التجاري رقم: 1010874412\nالاسم التجاري: شركة دانة للدفع الآجل\nالمدينة: الرياض\nالنشاط: الشراء الآن والدفع لاحقاً",
            "BUSINESS_PLAN": "خطة العمل ودراسة الجدوى 2026-2028\nرأس المال المدفوع: 5,500,000 ريال سعودي.\n"
                             "نستهدف نمو العملاء بنسبة 420% في السنة الأولى مع حد أقصى 5,000 ريال للعميل و4 أقساط.\n"
                             "تتم استضافة الأنظمة لدى مزود سحابي في فرانكفورت.\nعدد الموظفين: 46، نسبة السعوديين 52%.\n"
                             "تم تعيين مسؤول التزام مستقل يرفع تقاريره إلى لجنة المراجعة.",
            "FINANCIAL_STATEMENTS": "القوائم المالية المدققة للسنة المنتهية في 31 ديسمبر 2025\nرأس المال المدفوع 5,500,000 ريال.\nالمراجع الخارجي: مكتب محاسبة مرخص.",
            "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال وتمويل الإرهاب\nتقييم المخاطر حسب العملاء والمتاجر والقنوات.\n"
                              "إجراءات اعرف عميلك عبر التحقق من الهوية الوطنية، والعناية الواجبة المعززة للحالات عالية المخاطر.\n"
                              "تم تعيين مسؤول إبلاغ (MLRO). مدة حفظ السجلات عشر سنوات.",
            "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني المعتمدة من مجلس الإدارة\nالتشفير أثناء النقل والتخزين، والمصادقة متعددة العوامل، وخطة للاستجابة للحوادث.",
            "DATA_PROTECTION_POLICY": "سياسة حماية البيانات الشخصية\nأساس المعالجة: العقد والموافقة. تقليل البيانات. لم يُستكمل بعد تقييم مخاطر نقل البيانات خارج المملكة.",
        },
    },
    {
        "key": "wallet", "company_name_ar": "شركة واحة للمحافظ الرقمية", "company_name_en": "Waha Digital Wallet Co.",
        "commercial_registration": "4030561208", "city": "جدة", "contact_email": "licensing@wahawallet.sa",
        "website": "", "service_category": "DIGITAL_WALLET",
        "business_model": "محفظة رقمية للأفراد تتيح التحويلات بين المستخدمين والدفع لدى التجار عبر رمز الاستجابة السريعة وصرف الرواتب.",
        "target_customers": "المقيمون والمواطنون، مع التركيز على العمالة في المنشآت الصغيرة لصرف الرواتب.",
        "paid_up_capital_sar": 1_500_000, "expected_monthly_volume_sar": 80_000_000, "data_hosting_location": "الرياض",
        "uses_third_party_providers": True, "status": "SUBMITTED",
        "documents": {
            "COMMERCIAL_REGISTRATION": "السجل التجاري رقم: 4030561208\nالاسم التجاري: شركة واحة للمحافظ الرقمية\nالمدينة: جدة",
            "BUSINESS_PLAN": "خطة العمل\nرأس المال المدفوع: 1,500,000 ريال.\nنوع الترخيص المستهدف: مؤسسة نقود إلكترونية صغرى.\n"
                             "استضافة البيانات في مركز بيانات بالرياض.\nلا يوجد حالياً مسؤول التزام وسيتم التعيين بعد الحصول على الموافقة المبدئية.",
            "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني: التشفير أثناء النقل والتخزين، وإدارة الصلاحيات، وخطة للاستجابة للحوادث.",
            "OUTSOURCING_AGREEMENTS": "اتفاقية إسناد مع مزود معالجة بطاقات محلي، تتضمن حق التدقيق وخطة خروج مدتها 90 يوماً.",
        },
    },
    {
        "key": "openbank", "company_name_ar": "شركة مرسال للمصرفية المفتوحة", "company_name_en": "Mirsal Open Banking Co.",
        "commercial_registration": "1010932670", "city": "الرياض", "contact_email": "team@mirsal-ob.sa",
        "website": "", "service_category": "OPEN_BANKING",
        "business_model": "خدمة معلومات الحساب لتجميع الحسابات البنكية وتحليل التدفقات النقدية للمنشآت الصغيرة والمتوسطة بموافقة صريحة من العميل.",
        "target_customers": "المنشآت الصغيرة والمتوسطة والمحاسبون.",
        "paid_up_capital_sar": 2_000_000, "expected_monthly_volume_sar": 0, "data_hosting_location": "الرياض",
        "uses_third_party_providers": False, "status": "PENDING_HUMAN_REVIEW",
        "documents": {
            "COMMERCIAL_REGISTRATION": "Commercial Registration No: 1010932670\nالسجل التجاري رقم: 1010932670",
            "BUSINESS_PLAN": "خطة العمل\nرأس المال المدفوع: 2,000,000 ريال.\nاستضافة البيانات في الرياض.\nتم تعيين مسؤول التزام.\n"
                             "تأمين المسؤولية المهنية لدى شركة تأمين مرخصة.",
            "FINANCIAL_STATEMENTS": "قوائم مالية مدققة للسنة المنتهية 2025. رأس المال المدفوع 2,000,000 ريال.",
            "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال وتمويل الإرهاب مع مسؤول إبلاغ (MLRO) وتقييم مخاطر سنوي.",
            "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني وتقرير اختبار اختراق مستقل بتاريخ 2026-03، ومصادقة قوية للعملاء.",
            "DATA_PROTECTION_POLICY": "سياسة حماية البيانات الشخصية: الموافقة الصريحة قبل الوصول، وحذف البيانات عند سحب الموافقة، وتقليل البيانات.",
            "GOVERNANCE_STRUCTURE": "هيكل الحوكمة: مجلس إدارة من خمسة أعضاء ولجنة مراجعة ومسؤول التزام ومسؤول مخاطر.",
            "RISK_MANAGEMENT_FRAMEWORK": "إطار إدارة المخاطر: مؤشرات مخاطر رئيسية وحدود تحمل ومراجعة ربع سنوية.",
        },
    },
    {
        "key": "pay", "company_name_ar": "شركة نقطة للمدفوعات", "company_name_en": "Nuqta Payments Co.",
        "commercial_registration": "2050417793", "city": "الدمام", "contact_email": "hello@nuqtapay.sa",
        "website": "", "service_category": "DIGITAL_PAYMENTS",
        "business_model": "بوابة دفع إلكتروني للمتاجر الصغيرة مع تسوية يومية وربط مع منصات التجارة الإلكترونية.",
        "target_customers": "المتاجر الإلكترونية الصغيرة في المنطقة الشرقية.",
        "paid_up_capital_sar": 3_000_000, "expected_monthly_volume_sar": 20_000_000, "data_hosting_location": "Dublin, Ireland",
        "uses_third_party_providers": True, "status": "DRAFT",
        "documents": {"COMMERCIAL_REGISTRATION": "السجل التجاري رقم: 2050417793\nالاسم التجاري: شركة نقطة للمدفوعات\nالمدينة: الدمام"},
    },
    {
        "key": "lend", "company_name_ar": "شركة سند للتمويل المصغر", "company_name_en": "Sanad Microfinance Co.",
        "commercial_registration": "1010655081", "city": "الرياض", "contact_email": "risk@sanadfinance.sa",
        "website": "", "service_category": "LENDING",
        "business_model": "تمويل استهلاكي مصغر عبر تطبيق رقمي بحد أقصى 25,000 ريال للعميل وقرار ائتماني آلي خلال دقائق.",
        "target_customers": "الموظفون في القطاعين العام والخاص.",
        "paid_up_capital_sar": 12_000_000, "expected_monthly_volume_sar": 60_000_000, "data_hosting_location": "الرياض",
        "uses_third_party_providers": False, "status": "ADDITIONAL_INFORMATION_REQUIRED",
        "documents": {
            "COMMERCIAL_REGISTRATION": "السجل التجاري رقم: 1010655081\nالاسم التجاري: شركة سند للتمويل المصغر",
            "BUSINESS_PLAN": "خطة العمل\nرأس المال المدفوع: 12,000,000 ريال. تم تعيين مسؤول التزام. نمو متوقع 150%.\nاستضافة البيانات في الرياض.",
            "FINANCIAL_STATEMENTS": "قوائم مالية مدققة للسنة المنتهية 2025.",
            "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال وتمويل الإرهاب ومسؤول إبلاغ.",
        },
    },
    {
        "key": "remit", "company_name_ar": "شركة جسر الخليج للمدفوعات", "company_name_en": "Gulf Bridge Payments Co.",
        "commercial_registration": "4030728845", "city": "جدة", "contact_email": "ops@gulfbridgepay.sa", "website": "",
        "service_category": "DIGITAL_PAYMENTS", "business_model": "مدفوعات عابرة للحدود للمنشآت الصغيرة عبر بنوك مراسلة مرخصة.",
        "target_customers": "المستوردون والمصدرون الصغار.", "paid_up_capital_sar": 4_000_000, "expected_monthly_volume_sar": 45_000_000,
        "data_hosting_location": "جدة", "uses_third_party_providers": True, "status": "APPROVED_FOR_NEXT_REVIEW_STAGE",
        "documents": {
            "COMMERCIAL_REGISTRATION": "السجل التجاري رقم: 4030728845",
            "BUSINESS_PLAN": "خطة العمل\nرأس المال المدفوع: 4,000,000 ريال. ترخيص مؤسسة مدفوعات كبرى. تم تعيين مسؤول التزام.",
            "FINANCIAL_STATEMENTS": "قوائم مالية مدققة.",
            "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال وتمويل الإرهاب مع فحص قوائم العقوبات.",
            "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني المعتمدة.",
            "DATA_PROTECTION_POLICY": "سياسة حماية البيانات الشخصية.",
            "GOVERNANCE_STRUCTURE": "هيكل الحوكمة ولجنة المراجعة.",
            "OUTSOURCING_AGREEMENTS": "اتفاقيات البنوك المراسلة وخطة الخروج.",
            "RISK_MANAGEMENT_FRAMEWORK": "إطار إدارة المخاطر.",
        },
    },
]

ALL = ["BNPL", "DIGITAL_PAYMENTS", "DIGITAL_WALLET", "OPEN_BANKING", "LENDING"]


def _r(code, ar, en, cats, docs, sev, src, sec, rule=None):
    d = {"code": code, "title_ar": ar, "title_en": en, "service_categories": cats, "required_document_types": docs,
         "severity": sev, "source_document_code": src, "source_section": sec}
    if rule:
        d["rule"] = rule
    return d


# Configured requirement catalogue. Thresholds come from the cited official sources.
REQUIREMENTS = [
    # Buy now, pay later
    _r("BNPL-CAP", "الحد الأدنى لرأس المال: 5 ملايين ريال", "Minimum capital: SAR 5 million", ["BNPL"], ["FINANCIAL_STATEMENTS"],
       "HIGH", "SAMA-BNPL", "المادة 5 - رأس المال", {"field": "paid_up_capital_sar", "op": ">=", "value": 5_000_000}),
    _r("BNPL-LIC", "ملف الترخيص: السجل التجاري ودراسة الجدوى والهيكل التنظيمي", "Licence file: CR, feasibility study and organisation structure",
       ["BNPL"], ["COMMERCIAL_REGISTRATION", "BUSINESS_PLAN", "GOVERNANCE_STRUCTURE"], "HIGH", "SAMA-BNPL", "المادة 4 - طلب الترخيص"),
    _r("BNPL-POL", "السياسات الداخلية للائتمان والمخاطر", "Internal credit and risk policies", ["BNPL"], ["RISK_MANAGEMENT_FRAMEWORK"],
       "MEDIUM", "SAMA-BNPL", "المادة 13 - السياسات والإجراءات الداخلية"),
    _r("BNPL-OUT", "الالتزام بقواعد الإسناد", "Outsourcing rules compliance", ["BNPL"], ["OUTSOURCING_AGREEMENTS"],
       "MEDIUM", "SAMA-BNPL", "المادة 15 - الإسناد"),
    _r("BNPL-CP", "وحدة الشكاوى وحماية العملاء", "Complaints unit and consumer protection", ["BNPL"], ["CONSUMER_PROTECTION_POLICY"],
       "MEDIUM", "SAMA-BNPL", "المادة 17 - حماية العملاء وسرية البيانات"),
    # Payments and e-money
    _r("PAY-CAP", "الحد الأدنى لرأس المال: مليون ريال (صغرى) أو 3 ملايين (كبرى)", "Minimum capital: SAR 1M (micro PI) or 3M (major PI)",
       ["DIGITAL_PAYMENTS"], ["FINANCIAL_STATEMENTS"], "HIGH", "SAMA-PAYMENTS", "القسم 2 - الحد الأدنى لرأس المال الأولي",
       {"field": "paid_up_capital_sar", "op": ">=", "value": 1_000_000}),
    _r("EMI-CAP", "الحد الأدنى لرأس المال: مليونا ريال (صغرى) أو 10 ملايين (كبرى)", "Minimum capital: SAR 2M (micro EMI) or 10M (major EMI)",
       ["DIGITAL_WALLET"], ["FINANCIAL_STATEMENTS"], "HIGH", "SAMA-PAYMENTS", "القسم 2 - الحد الأدنى لرأس المال الأولي",
       {"field": "paid_up_capital_sar", "op": ">=", "value": 2_000_000}),
    _r("PAY-LIC", "ملف الترخيص: السجل التجاري وخطة العمل والملاءمة", "Licence file: CR, business plan and fit & proper",
       ["DIGITAL_PAYMENTS", "DIGITAL_WALLET"], ["COMMERCIAL_REGISTRATION", "BUSINESS_PLAN", "GOVERNANCE_STRUCTURE"], "HIGH",
       "SAMA-PAYMENTS", "القسم 5 - وثائق الترخيص"),
    # Open banking
    _r("OB-CAP", "الحد الأدنى لرأس المال: مليون ريال", "Minimum capital: SAR 1 million", ["OPEN_BANKING"], ["FINANCIAL_STATEMENTS"],
       "HIGH", "SAMA-OPENBANKING", "الفصل 5 - رأس المال", {"field": "paid_up_capital_sar", "op": ">=", "value": 1_000_000}),
    _r("OB-CONSENT", "الموافقة الصريحة وحذف البيانات عند سحبها", "Explicit consent and deletion on withdrawal", ["OPEN_BANKING"],
       ["DATA_PROTECTION_POLICY"], "HIGH", "SAMA-OPENBANKING", "الفصل 2 - موافقة العميل"),
    # Lending / microfinance
    _r("LEND-CAP", "الحد الأدنى لرأس المال: 10 ملايين ريال (تمويل مصغر بالتقنية المالية)", "Minimum capital: SAR 10M (fintech microfinance)",
       ["LENDING"], ["FINANCIAL_STATEMENTS"], "HIGH", "SAMA-MICROFINANCE", "المادة 4 - رأس مال شركة التمويل الاستهلاكي المصغر",
       {"field": "paid_up_capital_sar", "op": ">=", "value": 10_000_000}),
    _r("LEND-POL", "سياسات التمويل وتقييم الجدارة الائتمانية", "Finance and creditworthiness policies", ["LENDING"],
       ["RISK_MANAGEMENT_FRAMEWORK", "CONSUMER_PROTECTION_POLICY"], "MEDIUM", "SAMA-MICROFINANCE", "القسم 3 - سياسات التمويل"),
    _r("LEND-GOV", "هيكل الحوكمة والملاءمة لأعضاء المجلس", "Governance structure and board fit & proper", ["LENDING"],
       ["GOVERNANCE_STRUCTURE"], "MEDIUM", "SAMA-MICROFINANCE", "المادة 7 - الملاءمة المهنية"),
    # Cross-cutting
    _r("AML-01", "سياسة مكافحة غسل الأموال وتمويل الإرهاب ومسؤول الالتزام", "AML/CTF policy and compliance officer", ALL,
       ["AML_CTF_POLICY"], "HIGH", "SAMA-AML", "القسم 6 - الحوكمة الداخلية"),
    _r("CSF-01", "حوكمة الأمن السيبراني وسياسته المعتمدة", "Approved cybersecurity governance and policy", ALL,
       ["CYBERSECURITY_POLICY"], "HIGH", "SAMA-CSF", "القسم 3.1 - القيادة والحوكمة"),
    _r("CSF-TP", "ضوابط الأمن السيبراني للأطراف الخارجية", "Third-party cybersecurity controls", ["DIGITAL_PAYMENTS", "DIGITAL_WALLET"],
       ["OUTSOURCING_AGREEMENTS"], "MEDIUM", "SAMA-CSF", "القسم 3.4 - الأطراف الخارجية"),
    _r("PDPL-01", "سياسة حماية البيانات الشخصية", "Personal data protection policy", ALL, ["DATA_PROTECTION_POLICY"],
       "MEDIUM", "SDAIA-PDPL", "القسم 2 - التزامات جهة التحكم"),
]
