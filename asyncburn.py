#Nathan Rhoades, 10/11/2026, GNU GENERAL PUBLIC LICENSE

import os
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw
import time
import struct
import subprocess


class DigiBallImage():

    def __init__(self, output_folder, ball_diameter=2.25, tip_diameter=0.465, tip_curvature=0.358):

        self._output_folder = output_folder
        
        os.makedirs(self._output_folder, exist_ok=True)
        
        self._ball_diameter = ball_diameter      
        self._tip_diameter = tip_diameter
        self._tip_curvature = tip_curvature        
        
        self._ball_image = Image.open("assets/digiball_blank.png").convert("RGBA")

        width, height = self._ball_image.size
        self._radius = min(width,height)/2      

        self._blank_background = True
        self._file_index = 0

    def _draw(self,file_path,draw_ball=True,draw_tip=True,tip_angle=0,tip_percent=0):

        try:
            # Create ball image and draw            
            if draw_ball:                
                img = self._ball_image.copy()
            else:
                img = Image.new("RGBA", self._ball_image.size, (0, 0, 0, 0))
                
            draw = ImageDraw.Draw(img, "RGBA")
            
            center = (self._radius, self._radius)

            # Create grid
            if draw_ball:
                
                for i in range(1,7):
                    x1 = center[0] - self._radius*i/10
                    y1 = center[1] - self._radius*i/10
                    x2 = center[0] + self._radius*i/10
                    y2 = center[1] + self._radius*i/10
                    draw.ellipse([x1,y1,x2,y2], outline="black")
                for i in range(0,12):
                    x = center[0] + 0.6 * self._radius * np.cos(2 * np.pi * i / 12)
                    y = center[1] + 0.6 * self._radius * np.sin(2 * np.pi * i / 12)
                    draw.line([(x,y),center], fill="black")

            if draw_tip:
                
                # Calculate tip outline position
                ball_radius = self._ball_diameter / 2
                tip_radius = self._tip_diameter / 2

                tip_radius_curvature_ratio = self._tip_curvature / ball_radius

                t = tip_percent
                if t>55:
                    t=55
                r1 = ball_radius * t/100
                draw_offset = r1 * tip_radius_curvature_ratio
                px1 = 0
                s1 = r1 + draw_offset
                if (s1-tip_radius) > r1:
                    px1 = r1 + tip_radius
                else:
                    px1 = s1

                # Draw tip outline
                color = (0, 0, 0)
                ax = np.sin(np.pi / 180 * tip_angle)
                ay = -np.cos(np.pi / 180 * tip_angle)
                x = center[0] + self._radius * ax * px1 / ball_radius
                y = center[1] + self._radius * ay * px1 / ball_radius
                tr = self._radius * tip_radius / ball_radius

                alpha = 128
                pos = (x-tr,y-tr,2*tr,2*tr)

                x1 = x - tr
                y1 = y - tr
                x2 = x + tr
                y2 = y + tr
                
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)

                draw.ellipse([x1, y1, x2, y2], fill=(0, 0, 0, alpha))

                #draw.ellipse([x1,y1,x2,y2], fill=(0,0,0,alpha))

                # Calculate tip contact point
                x_contact = center[0] + self._radius * ax * r1 / ball_radius
                y_contact = center[1] + self._radius * ay * r1 / ball_radius
                tr /= 10
                if tr<3:
                    tr = 3

                # Draw tip contact point
                dot_radius = 4
                x1 = x_contact - dot_radius
                y1 = y_contact - dot_radius
                x2 = x_contact + dot_radius
                y2 = y_contact + dot_radius

                draw.ellipse([x1,y1,x2,y2], fill=(0, 255, 255, 255))

                img = Image.alpha_composite(img, overlay)
            
            img.save(file_path, format='PNG')

        except Exception as e:            
            print(f"An exception occurred: {e}")             
            
    def generate_image(self, draw_ball, draw_tip, spin_degrees, tip_percent):        
        
        #Parse data            
        file_path = "%s/%s.png"%(self._output_folder,self._file_index)
        self._file_index += 1

        #Generate image        
        self._draw(file_path, draw_ball, draw_tip, spin_degrees, tip_percent) 

class DataLog:

    def __init__(self, filename='digiball.log', starting_epoch=0, ending_epoch=0, data_video_delay_seconds=0):
        try:
            self._shotdata = None
            self._starting_epoch = starting_epoch
            self._ending_epoch = ending_epoch
            self._video_delay = data_video_delay_seconds
            self._file = open(filename, mode='r')
            self._parser()
            self._file.close()


        except FileNotFoundError:
            print('File %s not found.'%filename)

    def _parser(self):
        #Load and parse data into local memory as an array of dictionaries
        self._shotdata = []
        while 1:
            line = self._file.readline()
            if not line:
                break
            elif 'epoch' not in line:
                break
            chunks = line.split(',')
            chunks_dict = {}
            for chunk in chunks:
                label, data = chunk.split(':')
                if '{' in data:
                    values = data.strip('\r').strip('\n').strip('{').strip('}').strip(' ').split(' ')
                    values = list(map(int, values))
                    chunks_dict[label] = values
                elif '.' in data:
                    value = float(data)
                    chunks_dict[label] = value
                else:
                    value = int(data)
                    chunks_dict[label] = value
            epoch = chunks_dict['epoch']
            if epoch>=self._starting_epoch:
                if self._ending_epoch==0 or epoch<=self._ending_epoch:
                    chunks_dict['time'] = (epoch - self._starting_epoch)/1000 + self._video_delay
                    self._shotdata.append(chunks_dict)

    def _get_datetime(self, epoch):
        return datetime.fromtimestamp(epoch/1000)

    def get_all_shot_data(self):
        return self._shotdata

    def get_next_shot_data(self, time):
        for i in range(1,len(self._shotdata)):
            if self._shotdata[i]['time']>=time or i==(len(self._shotdata)-1):
                return self._shotdata[i-1]


class FilterWriter():

    def __init__(self,
                 video_input_filename='input.mp4',
                 video_output_filename='output.mp4',
                 filter_filename='filters.txt',
                 video_trim_start=None,
                 video_trim_duration=None):
        self._video_input_filename = video_input_filename
        self._video_output_filename = video_output_filename
        self._filter_file = open(filter_filename, mode='w')
        self._filter_filename = filter_filename
        self._video_trim_start = video_trim_start
        self._video_trim_duration = video_trim_duration
        self._filter_number = 0

        self._asset_file_names = []
        for i in range(0,56):
            self._asset_file_names.append('images/%i.png'%i)

        self._initialize_ffmpeg_command()

    def __del__(self):
        try:
            self._file.close()
        except:
            pass

    def _initialize_ffmpeg_command(self):
        assets = ''
        trim_start = ''
        trim_duration = ''
        if self._video_trim_start!=None:
            trim_start = " -ss %s"%self._video_trim_start
        if self._video_trim_duration!=None:
            trim_duration = " -t %s"%self._video_trim_duration

        for asset in self._asset_file_names:
            assets += ' -i %s'%asset
        self._ffmpeg_command = "ffmpeg -i %s%s -filter_complex_script %s%s%s %s"%(self._video_input_filename,
                                                                                  assets,
                                                                                  self._filter_filename,
                                                                                  trim_start,
                                                                                  trim_duration,
                                                                                  self._video_output_filename)

    def _write_filter(self, text):
        self._filter_file.write(text)
        self._filter_number+=1

    def get_ffmpeg_command(self):
        return self._ffmpeg_command

    def add_overlay(self, shot, overlay_start_time, overlay_end_time, scale=100):
        
        fstr = "%s[1:v]scale=%i:-1[bg];[%i:v]rotate=%.2f*PI/180:c=none:ow=rotw(iw):oh=roth(ih),scale=%i:-1[rotate];[bg][rotate]overlay=0:0[combined];%s[combined]overlay=0:0:enable='between(t,%.2f,%.2f)'";   
        
        if self._filter_number==0:
            inputv = '[0:v]'
            output = '[tmp]'
            link = ''
        else:
            inputv = '[tmp]'
            output = '[tmp]'
            link = ' [tmp];\n'

        if 'deg' in shot and 'tip' in shot:
            angle = shot['deg']
            pfc = shot['tip']
            p = int(np.round(pfc)) #20 images
            if p<0:
                p = 0
            elif p>55:
                p = 55
            fout = fstr%(link,scale,p+2,angle,scale,inputv,overlay_start_time,overlay_end_time)            
            self._write_filter(fout)



if __name__=="__main__":

    datafile = 'digiball.log'
    video_input_filename = 'video.mp4'
    video_delay = 0 #seconds
    start_data = 1791567522287 #epoch
    overlay_max_duration = 10 #seconds
    video_trim_start = "00:2:05"
    video_trim_duration = "00:10:00"
    overlay_scale = 100

    #Import objects for overlay design      
    print("Initializing filter writer from video %s"%video_input_filename)
    filt = FilterWriter(video_input_filename=video_input_filename,
                                             video_trim_start=video_trim_start,
                                             video_trim_duration=video_trim_duration)
    
    print("Importing data from %s"%datafile)
    log = DataLog(filename=datafile,starting_epoch=start_data,
                              data_video_delay_seconds=video_delay)
    shotdata = log.get_all_shot_data()
    
    #Generate images
    print("Generating DigiBall filter images")
    dbi = DigiBallImage(output_folder = "images")
    dbi.generate_image(True,False,0,0)
    for i in range(0,56):
        dbi.generate_image(False,True,0,i)

    #Extract data for overlays for each shot
    print("Building filters from shot data")
    for i in range(len(shotdata)-1):
        current_shot = shotdata[i]
        next_shot = shotdata[i+1]

        time_till_next_shot = next_shot['time']-current_shot['time']
        overlay_start_time = current_shot['time']
        if time_till_next_shot < overlay_max_duration:
            overlay_end_time = next_shot['time']
        else:
            overlay_end_time = overlay_start_time + overlay_max_duration

        filt.add_overlay(current_shot, overlay_start_time, overlay_end_time, overlay_scale)

    #Make ffmpeg run bat file
    batfilename = 'overlay_run.bat'
    f = open(batfilename,'w')
    cmd = filt.get_ffmpeg_command()    
    f.write(cmd)    
    f.close()
    
    print("Done. Run %s to burn DigiBall overlays."%batfilename)
    
    