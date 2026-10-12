"""
Generate a professionally styled Microsoft Word document (.docx)
containing the demo video scripts for NDSA officials, including
an upfront section on "How the System Works" behind the scenes.
"""
import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def create_document(output_path):
    doc = docx.Document()
    
    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        
    # Color Palette
    navy = RGBColor(15, 44, 89)      # #0F2C59
    slate = RGBColor(71, 85, 105)    # #475569
    dark_gray = RGBColor(30, 41, 59) # #1E293B
    teal = RGBColor(14, 116, 144)    # #0E7490

    # Header / Title Block
    title = doc.add_paragraph()
    title_run = title.add_run("DAM FAILURE & SAFETY NEWS WATCH")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = navy
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(2)

    subtitle = doc.add_paragraph()
    sub_run = subtitle.add_run("System Architecture, Operational Workflow & 2-Minute Demo Video Script")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(13)
    sub_run.font.bold = True
    sub_run.font.color.rgb = teal
    subtitle.paragraph_format.space_after = Pt(4)

    aud = doc.add_paragraph()
    aud_run = aud.add_run("Prepared for: National Dam Safety Authority (NDSA) Leadership & Technical Officers")
    aud_run.font.name = "Calibri"
    aud_run.font.size = Pt(10.5)
    aud_run.font.italic = True
    aud_run.font.color.rgb = slate
    aud.paragraph_format.space_after = Pt(12)

    # Document Overview Table
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False
    
    meta_data = [
        ("Target Audience", "Chairman, Member Secretaries, Directors & Technical Officers (NDSA & SDSOs)"),
        ("Architecture Summary", "Multi-source ingest (Google News, GDELT, YouTube) + NRSD 2026 Directory (6,814 Large Dams)"),
        ("Script Duration", "2-Minute High-Impact Video (~260 words at 130 wpm) with Teleprompter Text"),
        ("Key Limitation Addressed", "Semantic Noise / Irrelevant Non-Dam News (Metaphors, River Bunds vs. Large Dams)"),
    ]
    
    col_widths = [Inches(2.2), Inches(4.8)]
    for r_idx, (k, v) in enumerate(meta_data):
        row = meta_table.rows[r_idx]
        c0 = row.cells[0]
        c1 = row.cells[1]
        
        c0.width = col_widths[0]
        c1.width = col_widths[1]
        
        set_cell_background(c0, "F1F5F9")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=90, bottom=90, left=130, right=130)
        set_cell_margins(c1, top=90, bottom=90, left=130, right=130)
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(k)
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = navy
        
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(v)
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = dark_gray

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # ========================================================
    # SECTION 1: HOW THE SYSTEM WORKS (OPERATIONAL ARCHITECTURE)
    # ========================================================
    h_arch = doc.add_heading(level=1)
    h_arch_run = h_arch.add_run("1. How the System Works (Operational Architecture)")
    h_arch_run.font.name = "Calibri"
    h_arch_run.font.size = Pt(15)
    h_arch_run.font.color.rgb = navy
    h_arch_run.font.bold = True
    h_arch.paragraph_format.space_before = Pt(12)
    h_arch.paragraph_format.space_after = Pt(6)

    arch_intro = doc.add_paragraph()
    arch_intro_run = arch_intro.add_run(
        "The Dam Failure & Safety News Watch operates as an automated, multi-tiered intelligence pipeline designed to detect dam distress and incident reports across India before formal reporting channels engage:"
    )
    arch_intro_run.font.size = Pt(10)
    arch_intro_run.font.color.rgb = dark_gray
    arch_intro.paragraph_format.space_after = Pt(8)

    pipeline_steps = [
        ("Step 1: Multi-Source Crawling Across 13 Languages",
         "The ingestion engine queries Google News RSS editions, the GDELT global news database, and the YouTube Data API v3 across 13 Indian languages (Hindi, Marathi, Gujarati, Telugu, Tamil, Kannada, Malayalam, Bengali, Odia, Punjabi, Assamese, Urdu, and English)."),
         
        ("Step 2: Automated Scheduling (Daily at 7:00 AM IST)",
         "A background scheduler runs every morning at 7:00 AM IST, crawling the preceding 72 hours of news to capture overnight developments without manual intervention. Users can also trigger an on-demand live refresh at any time."),
         
        ("Step 3: Keyword Scoring & Entity Extraction",
         "Articles are evaluated using a curated hydrological dictionary (keywords.json). The system requires compound occurrences of structural dam terms (dam, barrage, reservoir, weir, check dam) and hazard verbs (breach, crack, collapse, leak, gate failure, inundation). Items meeting both criteria are scored as 'Relevant', while partial matches are tagged as 'Possible match'."),
         
        ("Step 4: NRSD Registry Cross-Referencing (6,814 Large Dams)",
         "Identified locations and structures are cross-referenced with the National Register of Large Dams (NRSD 2026). This allows the system to map news directly to official PIC codes, dam height, storage capacity, river basins, and administrative districts."),
         
        ("Step 5: Deduplication, AI Verification & Dashboard Delivery",
         "Stories are deduplicated by URL and headline hash in SQLite (dam_news.db). An optional AI classification layer (Anthropic Claude / LLM) verifies ambiguous reports, after which articles are rendered in the dashboard with one-click filtering, deep search, and CSV export.")
    ]

    t_steps = doc.add_table(rows=len(pipeline_steps) + 1, cols=2)
    t_steps.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_steps.autofit = False
    t_steps_widths = [Inches(2.2), Inches(4.8)]

    hdr_s = t_steps.rows[0]
    for c_idx, h_text in enumerate(["Pipeline Phase", "Technical Workflow & Operation"]):
        cell = hdr_s.cells[c_idx]
        cell.width = t_steps_widths[c_idx]
        set_cell_background(cell, "0F2C59")
        set_cell_margins(cell, top=110, bottom=110, left=120, right=120)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, (phase, detail) in enumerate(pipeline_steps, start=1):
        row = t_steps.rows[r_idx]
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([phase, detail]):
            cell = row.cells[c_idx]
            cell.width = t_steps_widths[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=90, bottom=90, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size = Pt(9)
            if c_idx == 0:
                r.font.bold = True
                r.font.color.rgb = navy
            else:
                r.font.color.rgb = dark_gray

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # ==========================================
    # SECTION 2: 2-MINUTE EXECUTIVE DEMO SCRIPT
    # ==========================================
    h1 = doc.add_heading(level=1)
    h1_run = h1.add_run("2. The 2-Minute Executive Demo Video Script")
    h1_run.font.name = "Calibri"
    h1_run.font.size = Pt(15)
    h1_run.font.color.rgb = navy
    h1_run.font.bold = True
    h1.paragraph_format.space_before = Pt(12)
    h1.paragraph_format.space_after = Pt(4)

    desc = doc.add_paragraph()
    desc_run = desc.add_run("Synchronized Screen Action vs. Voiceover Narration (~260 words at 130 wpm). Incorporates operational workflow at the opening.")
    desc_run.font.size = Pt(10)
    desc_run.font.italic = True
    desc_run.font.color.rgb = slate
    desc.paragraph_format.space_after = Pt(8)

    script_2m = [
        ("0:00 - 0:15\n(15 sec)", 
         "Start on Homepage.\nHover cursor over header, displaying 'Auto-updates daily at 7:00 AM IST' badge and the live headline feed.",
         "\"Respected NDSA officials: Under the Dam Safety Act, monitoring structural vulnerabilities across India’s 6,800+ large dams requires continuous situational awareness. Local dam distress—such as minor breaches, gate failures, or seepages—often surfaces in regional media hours before official channels receive word.\""),
        
        ("0:15 - 0:35\n(20 sec)",
         "How It Works Behind the Scenes:\nHighlight the automated scheduler badge, the language chips (13 Indian languages), and the live refresh button.",
         "\"Here is how it works: Every morning at 7:00 AM IST, an automated multi-threaded crawler scans national dailies, YouTube field reports, and vernacular press across 13 Indian languages. It evaluates articles against an engineering keyword dictionary and cross-references places with the National Register of Large Dams.\""),
        
        ("0:35 - 0:55\n(20 sec)",
         "NRSD Directory Lookup:\nClick top-left 'NRSD Dam Directory' box. Type 'Sardar Sarovar' or 'Tehri'. Click to open the Salient Features modal (PIC code, height, capacity, river basin).",
         "\"Officers can directly query the integrated NRSD database of 6,814 large dams. In one click, you can inspect a dam’s official salient features—such as PIC code, height, and storage—and jump immediately to incident reports linked to that structure.\""),
        
        ("0:55 - 1:15\n(20 sec)",
         "Filters, Search by Name & Export:\nSelect a State filter (e.g. Maharashtra). Click 'Search by name' in top bar, then point to 'Download as CSV' link.",
         "\"The platform offers state-wise filtering, historical timelines from today up to one year, deep incident searches by dam name, and instant CSV exports for official briefings and safety committee meetings.\""),
         
        ("1:15 - 1:40\n(25 sec)",
         "Current Shortcomings & Non-Dam News:\nPoint to a news card with the 'Possible match' badge or an article discussing canal overflow / political debates. Toggle 'Include possible matches' checkbox.",
         "\"Now, an honest look at our primary operational challenge: semantic noise and non-dam news. Because the scraper scans open journalism, it occasionally captures non-dam content:\n• Metaphorical headlines, like 'a dam of patience broke';\n• Local canal or river bund washouts that are not registered large dams;\n• Routine reservoir water levels and political water debates.\n\nTo keep your dashboard actionable, the platform automatically isolates uncertain items as 'Possible matches', backed by an AI classification layer to filter out noise.\""),
         
        ("1:40 - 2:00\n(20 sec)",
         "Closing & Value Proposition:\nZoom out to show the unified portal view (NRSD directory, clean feed, active filters). Fade to NDSA closing screen.",
         "\"The Dam Failure News Watch transforms thousands of fragmented news sources into a single, automated intelligence radar for the NDSA. We welcome your feedback to further calibrate precision. Thank you.\"")
    ]

    t2 = doc.add_table(rows=len(script_2m) + 1, cols=3)
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    t2.autofit = False

    t2_widths = [Inches(1.1), Inches(2.5), Inches(3.4)]
    headers = ["Timeline", "Visual / Screen Action", "Voiceover (Narration)"]
    
    hdr_row = t2.rows[0]
    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.width = t2_widths[c_idx]
        set_cell_background(cell, "0F2C59")
        set_cell_margins(cell, top=110, bottom=110, left=120, right=120)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, (t_box, act_box, narr_box) in enumerate(script_2m, start=1):
        row = t2.rows[r_idx]
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([t_box, act_box, narr_box]):
            cell = row.cells[c_idx]
            cell.width = t2_widths[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=90, bottom=90, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size = Pt(9)
            if c_idx == 0:
                r.font.bold = True
                r.font.color.rgb = navy
            elif c_idx == 2:
                r.font.italic = True
                r.font.color.rgb = dark_gray
            else:
                r.font.color.rgb = dark_gray

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # ==========================================
    # SECTION 3: 2-MINUTE TELEPROMPTER READ
    # ==========================================
    h2 = doc.add_heading(level=1)
    h2_run = h2.add_run("3. Continuous Voiceover Script (Teleprompter Ready)")
    h2_run.font.name = "Calibri"
    h2_run.font.size = Pt(15)
    h2_run.font.color.rgb = navy
    h2_run.font.bold = True
    h2.paragraph_format.space_before = Pt(12)
    h2.paragraph_format.space_after = Pt(6)

    box_p = doc.add_paragraph()
    box_run = box_p.add_run(
        "\"Respected NDSA officials: Under the Dam Safety Act, monitoring structural vulnerabilities across "
        "India’s 6,800+ large dams requires continuous situational awareness. Local dam distress—such as minor breaches, "
        "gate failures, or seepages—often surfaces in regional media hours before official channels receive word.\n\n"
        "Here is how it works: Every morning at 7:00 AM IST, an automated multi-threaded crawler scans national dailies, "
        "YouTube field reports, and vernacular press across 13 Indian languages. It evaluates articles against an engineering "
        "keyword dictionary and cross-references places with the National Register of Large Dams.\n\n"
        "Officers can directly query the integrated NRSD database of 6,814 large dams. In one click, you can inspect a dam’s "
        "official salient features—such as PIC code, height, and storage—and jump immediately to incident reports linked to that structure.\n\n"
        "The platform offers state-wise filtering, historical timelines from today up to one year, deep incident searches by dam name, "
        "and instant CSV exports for official briefings and safety committee meetings.\n\n"
        "Now, an honest look at our primary operational challenge: semantic noise and non-dam news. Because the scraper scans open "
        "journalism, it occasionally captures non-dam content: metaphorical headlines like 'a dam of patience broke'; local canal "
        "or river bund washouts that are not registered large dams; and routine reservoir water levels or political water debates. "
        "To keep your dashboard actionable, the platform automatically isolates uncertain items as 'Possible matches', backed by "
        "an AI classification layer to filter out noise.\n\n"
        "The Dam Failure News Watch transforms thousands of fragmented news sources into a single, automated intelligence radar "
        "for the NDSA. We welcome your feedback to further calibrate precision. Thank you.\""
    )
    box_run.font.name = "Calibri"
    box_run.font.size = Pt(10)
    box_run.font.italic = True
    box_run.font.color.rgb = dark_gray
    box_p.paragraph_format.line_spacing = 1.2
    box_p.paragraph_format.space_after = Pt(14)

    # ========================================================
    # SECTION 4: IN-DEPTH BREAKDOWN OF SHORTCOMINGS & MITIGATION
    # ========================================================
    h3 = doc.add_heading(level=1)
    h3_run = h3.add_run("4. Technical Deep-Dive: Shortcomings & Noise Mitigation")
    h3_run.font.name = "Calibri"
    h3_run.font.size = Pt(15)
    h3_run.font.color.rgb = navy
    h3_run.font.bold = True
    h3.paragraph_format.space_before = Pt(12)
    h3.paragraph_format.space_after = Pt(6)

    intro3 = doc.add_paragraph()
    intro3_run = intro3.add_run(
        "For NDSA technical reviews, the matrix below details the root causes of false positives in media aggregation and how the portal mitigates each case:"
    )
    intro3_run.font.size = Pt(10)
    intro3_run.font.color.rgb = dark_gray
    intro3.paragraph_format.space_after = Pt(8)

    shortcomings_data = [
        ("1. Metaphorical Language in Journalism",
         "Headlines such as 'Opposition breaches government dam of patience', 'Inflation dam bursts', or 'Film breaks box office dam'.",
         "Mitigated by compound scoring (requires both a physical dam noun AND a hydraulic failure verb) and secondary LLM semantic verification that discards political or sports metaphors."),
        
        ("2. River Embankments & Canal Bunds vs. Large Dams",
         "In regional languages (Hindi, Marathi, Gujarati, Telugu, Bengali), terms like 'bandh', 'bund', 'talav', or 'naala' frequently describe local irrigation canals, village check dams, or flood dykes.",
         "Filtered via structure isolation. Stories lacking an NRSD large dam context or verified large dam name are segregated as 'Possible match' rather than 'Relevant'."),
         
        ("3. Routine Reservoir Water Levels vs. Structural Failures",
         "During monsoon peaks, media reports reservoir inflows, routine gate opening for flood control, or municipal inundation without any structural risk or breach.",
         "Failure terms specifically prioritize distress criteria ('crack', 'seepage', 'collapse', 'embankment breach', 'gate stuck/failure') to distinguish normal operations from structural failure."),
         
        ("4. Publisher Paywalls & Aggregator Redirects",
         "Certain leading national and regional publications utilize dynamic javascript readers or subscription paywalls.",
         "The dashboard extracts and renders full title, source, publication timestamp, and snippet directly on the card so officers gain actionable context without being blocked by external paywalls.")
    ]

    t3 = doc.add_table(rows=len(shortcomings_data) + 1, cols=3)
    t3.alignment = WD_TABLE_ALIGNMENT.CENTER
    t3.autofit = False
    t3_widths = [Inches(1.8), Inches(2.6), Inches(2.6)]

    hdr3 = t3.rows[0]
    for c_idx, h_text in enumerate(["Noise Category / Shortcoming", "Typical Real-World Example", "System Safeguard / Mitigation"]):
        cell = hdr3.cells[c_idx]
        cell.width = t3_widths[c_idx]
        set_cell_background(cell, "0F2C59")
        set_cell_margins(cell, top=110, bottom=110, left=120, right=120)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, (cat, ex, mit) in enumerate(shortcomings_data, start=1):
        row = t3.rows[r_idx]
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate([cat, ex, mit]):
            cell = row.cells[c_idx]
            cell.width = t3_widths[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=90, bottom=90, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size = Pt(9)
            if c_idx == 0:
                r.font.bold = True
                r.font.color.rgb = navy
            else:
                r.font.color.rgb = dark_gray

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # Save
    doc.save(output_path)
    print(f"Document updated successfully at: {output_path}")

if __name__ == "__main__":
    out_file = os.path.abspath("NDSA_Dam_Safety_Portal_Demo_Script.docx")
    try:
        create_document(out_file)
    except PermissionError:
        alt_file = os.path.abspath("NDSA_Dam_Safety_Portal_Demo_Script_Updated.docx")
        print(f"Notice: '{out_file}' is currently open in Word. Saving to '{alt_file}' instead.")
        create_document(alt_file)
