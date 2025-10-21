import arcpy
import requests
import json
import os

#    print("Created by Christopher Pickett - 10-20-2025")
#    print("For any errors, go to https://github.com/cpickett101/arcgis-rest-extractor")   

def get_user_inputs():
    """
    Get user inputs for service URL and output location
    """
    print("=" * 70)
    print("ArcGIS REST Service Data Extractor")
    print("Created by Christopher Pickett - 10-20-2025")
    print("For any errors, go to https://github.com/cpickett101/arcgis-rest-extractor")   
    print("=" * 70)
    
    # Get Service URL
    print("\nEnter the ArcGIS REST MapServer URL:")
    print("Example: https://server/arcgis/rest/services/Folder/ServiceName/MapServer")
    service_url = input("Service URL: ").strip()
    
    # Remove trailing slash if present
    if service_url.endswith('/'):
        service_url = service_url[:-1]
    
    # Get Output Geodatabase path
    print("\nEnter the output file geodatabase path:")
    print("Example: C:\\GIS_Data\\MyData.gdb")
    output_gdb = input("Output GDB: ").strip()
    
    # Remove quotes if user copied path with quotes
    output_gdb = output_gdb.strip('"').strip("'")
    
    # Ask if user wants to extract all layers or specific ones
    print("\nDo you want to extract:")
    print("1. All layers")
    print("2. Specific layer(s) by ID")
    choice = input("Enter choice (1 or 2): ").strip()
    
    layer_ids = None
    if choice == '2':
        print("\nEnter layer ID(s) to extract (comma-separated):")
        print("Example: 0,5,10 or just 22")
        layer_input = input("Layer ID(s): ").strip()
        try:
            layer_ids = [int(x.strip()) for x in layer_input.split(',')]
        except ValueError:
            print("Invalid layer IDs. Extracting all layers instead.")
            layer_ids = None
    
    return service_url, output_gdb, layer_ids


def verify_service_url(service_url):
    """
    Verify that the service URL is accessible
    """
    try:
        print(f"\nVerifying service URL: {service_url}")
        response = requests.get(f"{service_url}?f=json", timeout=10)
        response.raise_for_status()
        service_info = response.json()
        
        print(f"✓ Service accessible: {service_info.get('mapName', 'Unknown')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"✗ Error accessing service: {e}")
        return False
    except Exception as e:
        print(f"✗ Error verifying service: {e}")
        return False


def get_layer_geometry_type(service_url, layer_id):
    """Get the geometry type for a specific layer"""
    try:
        layer_url = f"{service_url}/{layer_id}?f=json"
        response = requests.get(layer_url, timeout=10)
        response.raise_for_status()
        layer_info = response.json()
        return layer_info.get('geometryType', None)
    except Exception as e:
        print(f"Error getting geometry type for layer {layer_id}: {e}")
        return None


def extract_layer_data(service_url, layer_id, output_fc):
    """
    Extract data from a specific layer in the ArcGIS REST service
    """
    
    # Get layer metadata first
    layer_url = f"{service_url}/{layer_id}"
    
    try:
        metadata_response = requests.get(f"{layer_url}?f=json", timeout=10)
        metadata_response.raise_for_status()
        layer_info = metadata_response.json()
    except Exception as e:
        print(f"  ✗ Error getting layer metadata: {e}")
        return False
    
    geometry_type = layer_info.get('geometryType', 'esriGeometryPolygon')
    
    # Construct query URL
    query_url = f"{layer_url}/query"
    
    # Parameters for the query
    params = {
        'where': '1=1',
        'outFields': '*',
        'returnGeometry': 'true',
        'f': 'json',
        'outSR': '2278'
    }
    
    try:
        print(f"  Querying layer {layer_id}...")
        response = requests.get(query_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for errors in response
        if 'error' in data:
            print(f"  ✗ Error from server: {data['error'].get('message', 'Unknown error')}")
            return False
        
        # Check if we have features
        if 'features' not in data or len(data['features']) == 0:
            print(f"  ⚠ No features found in layer {layer_id}")
            return False
        
        # Save JSON to temporary file
        temp_json = os.path.join(arcpy.env.scratchFolder, f"temp_layer_{layer_id}.json")
        with open(temp_json, 'w') as f:
            json.dump(data, f)
        
        # Convert JSON to features
        arcpy.conversion.JSONToFeatures(temp_json, output_fc)
        
        # Get feature count
        count = int(arcpy.management.GetCount(output_fc)[0])
        print(f"  ✓ Successfully extracted {count} features")
        print(f"  ✓ Geometry type: {geometry_type}")
        
        # Clean up temp file
        if os.path.exists(temp_json):
            os.remove(temp_json)
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error querying layer: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error processing layer: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_all_layers(service_url, output_gdb, layer_ids=None):
    """
    Extract all layers or specific layers from the map service
    """
    
    # Get service metadata
    metadata_url = f"{service_url}?f=json"
    
    try:
        response = requests.get(metadata_url, timeout=10)
        response.raise_for_status()
        service_info = response.json()
        
        # Create output geodatabase if it doesn't exist
        if not arcpy.Exists(output_gdb):
            gdb_path = os.path.dirname(output_gdb)
            gdb_name = os.path.basename(output_gdb)
            
            # Create directory if it doesn't exist
            if not os.path.exists(gdb_path):
                os.makedirs(gdb_path)
                print(f"Created directory: {gdb_path}")
            
            arcpy.management.CreateFileGDB(gdb_path, gdb_name)
            print(f"Created geodatabase: {output_gdb}")
        else:
            print(f"Using existing geodatabase: {output_gdb}")
        
        # Get layers to extract
        all_layers = service_info.get('layers', [])
        
        if layer_ids:
            # Filter to only requested layers
            layers = [l for l in all_layers if l['id'] in layer_ids]
            print(f"\nExtracting {len(layers)} specified layer(s) out of {len(all_layers)} total layers")
        else:
            layers = all_layers
            print(f"\nExtracting all {len(layers)} layers")
        
        if not layers:
            print("No layers found to extract!")
            return
        
        # Track results
        success_count = 0
        fail_count = 0
        
        # Extract each layer
        for i, layer in enumerate(layers, 1):
            layer_id = layer['id']
            layer_name = layer['name'].replace(' ', '_').replace('-', '_')
            
            # Remove special characters that aren't allowed in feature class names
            layer_name = ''.join(c for c in layer_name if c.isalnum() or c == '_')
            
            # Create valid feature class name
            layer_name = arcpy.ValidateTableName(layer_name, output_gdb)
            output_fc = os.path.join(output_gdb, layer_name)
            
            print(f"\n[{i}/{len(layers)}] {'='*60}")
            print(f"Layer ID: {layer_id}")
            print(f"Layer Name: {layer['name']}")
            print(f"Output: {output_fc}")
            print(f"{'='*60}")
            
            if extract_layer_data(service_url, layer_id, output_fc):
                success_count += 1
            else:
                fail_count += 1
        
        # Summary
        print(f"\n\n{'='*70}")
        print("EXTRACTION COMPLETE!")
        print(f"{'='*70}")
        print(f"✓ Successfully extracted: {success_count} layer(s)")
        if fail_count > 0:
            print(f"✗ Failed: {fail_count} layer(s)")
        print(f"📁 Output location: {output_gdb}")
        print(f"{'='*70}")
        
    except Exception as e:
        print(f"\n✗ Error during extraction: {e}")
        import traceback
        traceback.print_exc()


def main():
    """
    Main execution function
    """
    try:
        # Get user inputs
        service_url, output_gdb, layer_ids = get_user_inputs()
        
        # Verify service is accessible
        if not verify_service_url(service_url):
            print("\n✗ Cannot proceed - service is not accessible")
            return
        
        # Confirm with user
        print(f"\n{'='*70}")
        print("CONFIGURATION SUMMARY")
        print(f"{'='*70}")
        print(f"Service URL: {service_url}")
        print(f"Output GDB: {output_gdb}")
        if layer_ids:
            print(f"Layer IDs: {', '.join(map(str, layer_ids))}")
        else:
            print("Extracting: All layers")
        print(f"{'='*70}")
        
        proceed = input("\nProceed with extraction? (yes/no): ").strip().lower()
        if proceed not in ['yes', 'y']:
            print("Extraction cancelled by user.")
            return
        
        # Start extraction
        print(f"\n{'='*70}")
        print("STARTING EXTRACTION...")
        print(f"{'='*70}")
        
        extract_all_layers(service_url, output_gdb, layer_ids)
        
    except KeyboardInterrupt:
        print("\n\nExtraction cancelled by user (Ctrl+C)")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


# Run the script
if __name__ == "__main__":
    main()
