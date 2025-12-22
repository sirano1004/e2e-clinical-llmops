NOTE_STYLES = """
<style>
    /* 1. Basic header and items (keep existing) */
    .note-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0.5rem 0 0.25rem;
    }
    .note-item {
        margin: 0.2rem 0;
        padding-left: 0.5rem;
        color: #111827;
        font-size: 0.92rem;
        line-height: 1.6; /* Secure line spacing for tooltip readability */
    }
    .note-divider {
        border-bottom: 1px dashed #e2e8f0;
        margin: 0.65rem 0;
    }

    /* 2. [NEW] Warning highlight (highlighter effect) */
    .warning-highlight {
        background-color: #fff9c4; /* Light yellow background */
        border-bottom: 2px solid #fbc02d; /* Dark yellow underline */
        cursor: help; /* Change cursor to question mark */
        position: relative; /* Tooltip position reference point */
        border-radius: 3px;
        padding: 0 2px;
        color: #000;
        display: inline; /* Maintain text flow */
    }

    /* 3. [NEW] Tooltip box (hidden normally) */
    .warning-highlight .tooltip-text {
        visibility: hidden;
        width: 280px; /* Box width */
        background-color: #1f2937; /* Dark gray/black background */
        color: #fff; /* White text */
        text-align: left;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 0.85rem;
        font-weight: 400;
        line-height: 1.4;

        /* Positioning (directly above text, center) */
        position: absolute;
        z-index: 9999; 
        bottom: 135%; /* Float above text */
        left: 50%;
        transform: translateX(-50%); /* Horizontal center alignment */
        
        /* Animation */
        opacity: 0;
        transition: opacity 0.2s ease-in-out;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        pointer-events: none; /* Prevent tooltip from intercepting mouse events */
    }

    /* 4. Show tooltip on mouse hover */
    .warning-highlight:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
    }

    /* 5. Tooltip tail (arrow shape) */
    .warning-highlight .tooltip-text::after {
        content: "";
        position: absolute;
        top: 100%; /* Directly below tooltip box */
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: #1f2937 transparent transparent transparent;
    }
</style>
"""