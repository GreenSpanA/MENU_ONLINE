import os
from flask import Flask, request, redirect, url_for
from werkzeug.utils import secure_filename
from pdf_reader import get_name, get_coordinates, get_diff3, round3, pdf_boundary_boxes
import pdfquery
import pandas as pd
from flask import send_from_directory

from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))
pdfmetrics.registerFont(TTFont('VeraBd', 'VeraBd.ttf'))
pdfmetrics.registerFont(TTFont('VeraIt', 'VeraIt.ttf'))
pdfmetrics.registerFont(TTFont('VeraBI', 'VeraBI.ttf'))


UPLOAD_FOLDER = 'UPLOAD_FOLDER/'
ALLOWED_EXTENSIONS = set(['pdf'])
pdf_name = 'pdf_temp.pdf'
pdf_input_path = 'UPLOAD_FOLDER\pdf_temp.pdf'
pdf_output_path = 'temp.pdf'
min_dish_count = 5

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

base_path = os.path.abspath(os.path.dirname(__file__))
upload_path = os.path.join(base_path, app.config['UPLOAD_FOLDER'])
app = Flask(__name__)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_path, pdf_name))
            return redirect(url_for('uploaded_file',
                                    filename=pdf_output_path))
    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form action="" method=post enctype=multipart/form-data>
      <p><input type=file name=file>
         <input type=submit value=Upload>
    </form>
    '''

# Open file in uploads
#@app.route('/uploads/<filename>')
#def uploaded_file(filename):
#    return send_from_directory(upload_path,
#                               filename)



#@app.route('/uploads/<filename>')
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Read fie
    pdf = pdfquery.PDFQuery('UPLOAD_FOLDER/pdf_temp.pdf')
    pdf.load()

    # Save xml tree
    pdf.tree.write('UPLOAD_FOLDER/test.xml', pretty_print=True)
    pq_items = pdf.pq('LTTextBoxVertical, LTTextLineHorizontal')
    items = pd.DataFrame(
        columns=['name', 'x0', 'x1', 'y0', 'y1', 'height', 'width', 'page_num'])

    for pq in pq_items:
        page_pq = next(pq.iterancestors('LTPage'))  # Use just the first ancestor
        page_num = page_pq.layout.pageid

        cur_str_item = str(pq.layout)

        tmp_items = pd.DataFrame([[
            get_name(cur_str_item),
            float(get_coordinates(cur_str_item)[0]),
            float(get_coordinates(cur_str_item)[2]),
            float(get_coordinates(cur_str_item)[1]),
            float(get_coordinates(cur_str_item)[3])
        ]],
            columns=['name', 'x0', 'x1', 'y0', 'y1'])

        # tmp_items['height'] = tmp_items['y1'] - tmp_items['y0']
        # tmp_items['width'] = tmp_items['x1'] - tmp_items['x0']

        tmp_items['height'] = get_diff3(tmp_items['y1'], tmp_items['y0'])
        tmp_items['width'] = get_diff3(tmp_items['x1'], tmp_items['x0'])

        tmp_items['page_num'] = page_num

        items = items.append(tmp_items, ignore_index=True)

    # PDF converted to DF
    items = items.sort_values(['page_num', 'x0', 'y1'], ascending=[True, True, False])
    items.reset_index(inplace=True, drop=True)

    #H destribution
    heights = pd.crosstab(index=items["height"], columns="count")
    heights = heights[heights['count'] > 1]

    cat_h = round3(max(heights[heights['count'] >= min_dish_count].index.values))
    tmp = heights[heights['count'] >= min_dish_count].index.values
    item_h = round3(max(tmp[tmp < cat_h]))

    pdf_boundary_boxes(
        df=items, path_input=pdf_input_path, path_output='UPLOAD_FOLDER/temp.pdf', r=50, g=0, b=100)

    #return 'Done'
    return send_from_directory(upload_path, 'temp.pdf')


if __name__ == '__main__':
	app.run(host='0.0.0.0',  port=8000)
