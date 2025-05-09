from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from models.scheduler import run_optimization
import pandas as pd
import os
from datetime import datetime
import traceback

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SCHEDULE_FOLDER'] = 'schedules'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SCHEDULE_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_schedule():
    if 'demand_file' not in request.files or 'nurses_file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No files uploaded'})
    
    demand_file = request.files['demand_file']
    nurses_file = request.files['nurses_file']
    
    if demand_file.filename == '' or nurses_file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected files'})
    
    if not (allowed_file(demand_file.filename) and allowed_file(nurses_file.filename)):
        return jsonify({'status': 'error', 'message': 'Only Excel files allowed'})
    
    try:
        # Save uploaded files
        demand_filename = secure_filename(f"demand_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        nurses_filename = secure_filename(f"nurses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        demand_path = os.path.join(app.config['UPLOAD_FOLDER'], demand_filename)
        nurses_path = os.path.join(app.config['UPLOAD_FOLDER'], nurses_filename)
        
        demand_file.save(demand_path)
        nurses_file.save(nurses_path)
        
        # Run optimization
        schedule_df, metrics = run_optimization(demand_path, nurses_path)
        
        # Add metadata
        schedule_df['schedule_generated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save schedule
        schedule_filename = f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        schedule_path = os.path.join(app.config['SCHEDULE_FOLDER'], schedule_filename)
        schedule_df.to_excel(schedule_path, index=False)
        
        # Clean up uploads
        os.remove(demand_path)
        os.remove(nurses_path)
        
        return jsonify({
            'status': 'success',
            'schedule': schedule_df.head(100).to_dict('records'),
            'metrics': metrics,
            'download_url': f'/download/{schedule_filename}',
            'period_start': schedule_df['period_start'].iloc[0],
            'period_end': schedule_df['period_end'].iloc[0]
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/download/<filename>')
def download_schedule(filename):
    try:
        return send_file(
            os.path.join(app.config['SCHEDULE_FOLDER'], filename),
            as_attachment=True,
            download_name=f"nurse_schedule_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        )
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)