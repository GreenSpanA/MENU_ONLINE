import os
from flask import Flask, request, redirect, url_for
from werkzeug.utils import secure_filename
from pdf_reader import get_name, get_coordinates, get_diff3, round3, \
    pdf_boundary_boxes, mean_char, collapse_rows
import pdfquery
import pandas as pd
from flask import send_from_directory

import urllib.request

from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))
pdfmetrics.registerFont(TTFont('VeraBd', 'VeraBd.ttf'))
pdfmetrics.registerFont(TTFont('VeraIt', 'VeraIt.ttf'))
pdfmetrics.registerFont(TTFont('VeraBI', 'VeraBI.ttf'))


UPLOAD_FOLDER = 'UPLOAD_FOLDER/'
ALLOWED_EXTENSIONS = set(['pdf'])
df_name = 'pdf_temp.pdf'
urllib.request.urlretrieve('https://richardi.azurewebsites.net/Home/GetReport/menu.pdf', 'UPLOAD_FOLDER/menu.pdf')
pdf_input_path = 'UPLOAD_FOLDER/menu.pdf'
#pdf_input_path = 'UPLOAD_FOLDER/pdf_temp.pdf'
pdf_output_path = 'temp_dishes_prices.pdf'
min_dish_count = 5
pdf_name = 'pdf_temp.pdf'

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
        #file = 'https://richardi.azurewebsites.net/Home/GetReport/menu.pdf'
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
    pdf = pdfquery.PDFQuery('UPLOAD_FOLDER/menu.pdf')
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

    # Plot all boxes
    pdf_boundary_boxes(
        df=items, path_input=pdf_input_path, path_output='UPLOAD_FOLDER/temp.pdf', r=50, g=0, b=100)

    ########################      Get categoties ####################################

    cat_list = items[items['height'].between(0.99 * cat_h, 1.01 * cat_h)]
    cat_char_w = cat_list.apply(lambda row: mean_char(row['width'], row['name']), axis=1).median()
    cat_char_w_max = cat_list.apply(lambda row: mean_char(row['width'], row['name']), axis=1).max()

    #Collapse  rows with  cat
    cat_list = collapse_rows(cat_list, sense=1.03)
    cat_list = cat_list.sort_values(['page_num', 'y1', 'x0'], ascending=[True, False, True])

    filter = cat_list["name"] != ' '
    cat_list = cat_list[filter]
    cat_list = cat_list.reset_index(drop=True)

    #Draw categories boxes
    pdf_boundary_boxes(df=cat_list, path_input=pdf_input_path, show_height=False,
                       show_number=True, path_output='UPLOAD_FOLDER/temp1.pdf')


    #################### Get items ###############################################

    items_list = items[items['height'].between(0.99 * item_h, 1.01 * item_h)]
    items_list = items_list.reset_index(drop=True)
    items_list = collapse_rows(items_list)

    # Delete empty items
    filter = items_list["name"] != ' '
    items_list = items_list[filter]
    items_list = items_list.reset_index(drop=True)

    # Get dishes
    patternDel = "^[0-9 \. \/]+$"
    filter = items_list['name'].str.contains(patternDel)
    dishes_list = items_list[~filter]
    dishes_list = dishes_list.reset_index(drop=True)

    # Dishes to layout
    pdf_boundary_boxes(
        df=dishes_list,
        path_input="UPLOAD_FOLDER/temp1.pdf",
        path_output="UPLOAD_FOLDER/temp_dishes.pdf",
        r=0,
        g=0,
        b=230)

    # Get prices
    prices_list = items_list[~items_list.name.isin(dishes_list.name)]
    prices_list = prices_list.reset_index(drop=True)

    # Prices to layout
    pdf_boundary_boxes(
        df=prices_list,
        path_input="UPLOAD_FOLDER/temp_dishes.pdf",
        path_output="UPLOAD_FOLDER/temp_dishes_prices.pdf",
        r=230,
        g=0,
        b=0)

    #return 'Done'
    return send_from_directory(upload_path, 'temp_dishes_prices.pdf')


if __name__ == '__main__':
	app.run(host='0.0.0.0',  port=8000)
