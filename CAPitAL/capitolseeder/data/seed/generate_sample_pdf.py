from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_fixtures():
    seed_dir = Path(__file__).parent
    
    # Create sample scanned image (simulating a handwritten/scanned PTR report)
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Add title and table headers
    draw.text((30, 30), "UNITED STATES HOUSE OF REPRESENTATIVES", fill=(0, 0, 0))
    draw.text((30, 50), "PERIODIC TRANSACTION REPORT (PTR)", fill=(0, 0, 0))
    draw.line([(30, 75), (770, 75)], fill=(50, 50, 50), width=2)
    
    # Table headers
    draw.text((30, 90), "Owner", fill=(0, 0, 0))
    draw.text((100, 90), "Ticker", fill=(0, 0, 0))
    draw.text((180, 90), "Asset Description", fill=(0, 0, 0))
    draw.text((380, 90), "Tx Type", fill=(0, 0, 0))
    draw.text((460, 90), "Date", fill=(0, 0, 0))
    draw.text((560, 90), "Amount Bracket", fill=(0, 0, 0))
    draw.line([(30, 115), (770, 115)], fill=(100, 100, 100), width=1)
    
    # Row 1 (Pelosi NVDA)
    draw.text((30, 130), "SP", fill=(20, 20, 20))
    draw.text((100, 130), "NVDA", fill=(20, 20, 20))
    draw.text((180, 130), "NVIDIA Corp Call Option 120C", fill=(20, 20, 20))
    draw.text((380, 130), "P", fill=(20, 20, 20))
    draw.text((460, 130), "06/26/2024", fill=(20, 20, 20))
    draw.text((560, 130), "$1,000,001 - $5,000,000", fill=(20, 20, 20))
    
    # Row 2 (Tuberville LMT)
    draw.text((30, 160), "JT", fill=(20, 20, 20))
    draw.text((100, 160), "LMT", fill=(20, 20, 20))
    draw.text((180, 160), "Lockheed Martin Common", fill=(20, 20, 20))
    draw.text((380, 160), "P", fill=(20, 20, 20))
    draw.text((460, 160), "07/10/2024", fill=(20, 20, 20))
    draw.text((560, 160), "$100,001 - $250,000", fill=(20, 20, 20))
    
    # Save PNG and PDF version
    scanned_png = seed_dir / "sample_ptr_scanned.png"
    img.save(scanned_png)
    
    digital_pdf = seed_dir / "sample_ptr_digital.pdf"
    img.save(digital_pdf, "PDF", resolution=100.0)
    print(f"Generated fixtures at {seed_dir}")

if __name__ == "__main__":
    generate_fixtures()
