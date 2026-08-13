import os
import hashlib
import sys

def generate_addons_xml():
    # Directories containing the packaged addon sources
    repo_id = sys.argv[1] if len(sys.argv) > 1 else 'repository.jiotvdirect'
    source_dirs = ['temp/plugin.kodi.jiotv', f'temp_repo/{repo_id}']
    output_dir = "repo"
    addons_xml_path = os.path.join(output_dir, "addons.xml")
    addons_md5_path = os.path.join(output_dir, "addons.xml.md5")
    
    # Start the XML
    xml_content = u'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    
    for s_dir in source_dirs:
        addon_xml = os.path.join(s_dir, "addon.xml")
        if os.path.exists(addon_xml):
            with open(addon_xml, 'r', encoding='utf-8') as f:
                content = f.read()
                # Remove the XML header if present
                if '<?xml' in content:
                    content = content.split('?>', 1)[1].strip()
                xml_content += content + u'\n'
    
    xml_content += u'</addons>\n'
    
    # Save addons.xml
    with open(addons_xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)
        
    # Generate MD5 (exactly 32 chars, no newline)
    md5_hash = hashlib.md5(xml_content.encode('utf-8')).hexdigest()
    with open(addons_md5_path, 'w', encoding='utf-8') as f:
        f.write(md5_hash)
    
    print(f"Generated {addons_xml_path} and {addons_md5_path}")

if __name__ == "__main__":
    generate_addons_xml()
